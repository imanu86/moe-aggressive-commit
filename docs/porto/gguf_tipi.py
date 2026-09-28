"""Legge SOLO le intestazioni di uno o piu' shard GGUF e riassume i byte per tipo di tensore e per famiglia
(esperti instradati, esperti condivisi, attenzione/densi, embedding/uscita, PLE, testa MTP). Nessuna scrittura.

Uso (28/9/2026, sul daily GSQ-RCO): python gguf_tipi.py <shard1.gguf> [<shard2.gguf> ...]
I byte di ogni tensore sono la distanza fra offset consecutivi (padding compreso). Tipi dall'enum di ggml.h dell'albero
p11 (40 NVFP4, 41 Q1_0, 42 Q2_0); un tipo sconosciuto compare come «tipoN»."""
import struct
import sys
from collections import defaultdict
from pathlib import Path

NOMI = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K",
        12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S",
        20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64",
        29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0", 39: "MXFP4", 40: "NVFP4", 41: "Q1_0", 42: "Q2_0"}


class R:
    def __init__(self, f):
        self.f = f

    def u(self, fmt):
        n = struct.calcsize(fmt)
        return struct.unpack("<" + fmt, self.f.read(n))[0]

    def s(self):
        n = self.u("Q")
        return self.f.read(n).decode("utf-8", "replace")

    def val(self, t):
        if t == 8:
            return self.s()
        if t == 9:
            et, n = self.u("I"), self.u("Q")
            if et == 8:
                return [self.s() for _ in range(n)]
            fmt = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}[et]
            sz = struct.calcsize(fmt)
            if n > 64:
                self.f.seek(n * sz, 1)
                return f"<array {n}>"
            return [self.u(fmt) for _ in range(n)]
        fmt = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}[t]
        return self.u(fmt)


def famiglia(nome):
    if "nextn" in nome or "mtp" in nome:
        return "testa MTP"
    if "_exps" in nome:
        return "esperti instradati"
    if "_shexp" in nome or "shared" in nome:
        return "esperti condivisi"
    if nome.startswith("token_embd") or nome.startswith("output"):
        return "embedding/uscita"
    if "per_layer" in nome or "ple" in nome.lower():
        return "PLE"
    return "densi (attenzione, norme, router...)"


def leggi(path):
    with open(path, "rb") as f:
        r = R(f)
        assert f.read(4) == b"GGUF", path
        ver, nt, nkv = r.u("I"), r.u("Q"), r.u("Q")
        meta = {}
        for _ in range(nkv):
            k = r.s()
            t = r.u("I")
            meta[k] = r.val(t)
        tens = []
        for _ in range(nt):
            nome = r.s()
            nd = r.u("I")
            dims = [r.u("Q") for _ in range(nd)]
            tipo = r.u("I")
            off = r.u("Q")
            tens.append([nome, dims, tipo, off])
        al = meta.get("general.alignment", 32)
        inizio = (f.tell() + al - 1) // al * al
    dim = Path(path).stat().st_size
    tens.sort(key=lambda x: x[3])
    for i, t in enumerate(tens):
        fine = tens[i + 1][3] if i + 1 < len(tens) else dim - inizio
        t.append(fine - t[3])
    return meta, tens


def main():
    per_tipo = defaultdict(int)
    per_fam = defaultdict(lambda: defaultdict(int))
    meta0 = None
    for p in sys.argv[1:]:
        meta, tens = leggi(p)
        meta0 = meta0 or meta
        for nome, dims, tipo, off, byte in tens:
            tn = NOMI.get(tipo, f"tipo{tipo}")
            per_tipo[tn] += byte
            per_fam[famiglia(nome)][tn] += byte
    arch = meta0.get("general.architecture")
    print("arch:", arch, "| nome:", meta0.get("general.name"))
    for k in sorted(meta0):
        if k.startswith(f"{arch}.") and any(x in k for x in ("expert", "block_count", "context_length")):
            print(f"  {k} = {meta0[k]}")
    tot = sum(per_tipo.values())
    print(f"\nTOTALE {tot / 2**30:.2f} GiB")
    for tn, b in sorted(per_tipo.items(), key=lambda x: -x[1]):
        print(f"  {tn:<9} {b / 2**30:8.2f} GiB")
    print("\nPer famiglia:")
    for fam, d in sorted(per_fam.items(), key=lambda x: -sum(x[1].values())):
        s = sum(d.values())
        dett = ", ".join(f"{tn} {b / 2**30:.2f}" for tn, b in sorted(d.items(), key=lambda x: -x[1]))
        print(f"  {fam:<38} {s / 2**30:8.2f} GiB  [{dett}]")


if __name__ == "__main__":
    main()
