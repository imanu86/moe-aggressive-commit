"""P10 cella 3 - estrae dal GGUF i byte grezzi di un tensore di esperti (iq2_s o iq4_nl)
per darli in pasto al microbanco CUDA. Legge SOLO l'intestazione piu' la fetta richiesta.

Uso:
    python estrai_iq2s_p10.py --gguf <primo shard> --elenca
    python estrai_iq2s_p10.py --gguf <primo shard> --tensore blk.10.ffn_gate_exps.weight \
        --esperti 48 --out log/pesi_iq2s.bin
"""
import argparse
import json
import struct
from pathlib import Path

TIPI = {0: "f32", 1: "f16", 8: "q8_0", 10: "q2_k", 11: "q3_k", 12: "q4_k", 13: "q5_k",
        14: "q6_k", 16: "iq2_xxs", 17: "iq2_xs", 18: "iq3_xxs", 19: "iq1_s", 20: "iq4_nl",
        21: "iq3_s", 22: "iq2_s", 23: "iq4_xs", 29: "iq1_m", 30: "bf16"}
BLOCCHI = {"f32": (1, 4), "f16": (1, 2), "bf16": (1, 2), "q8_0": (32, 34),
           "q2_k": (256, 84), "q3_k": (256, 110), "q4_k": (256, 144), "q5_k": (256, 176),
           "q6_k": (256, 210), "iq2_xxs": (256, 66), "iq2_xs": (256, 74), "iq2_s": (256, 82),
           "iq3_xxs": (256, 98), "iq3_s": (256, 110), "iq1_s": (256, 50), "iq1_m": (256, 56),
           "iq4_nl": (32, 18), "iq4_xs": (256, 136)}


class Lettore:
    def __init__(self, f):
        self.f = f

    def u32(self):
        return struct.unpack("<I", self.f.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.f.read(8))[0]

    def stringa(self):
        n = self.u64()
        return self.f.read(n).decode("utf-8", errors="replace")

    def valore(self, t):
        if t == 0:   return struct.unpack("<B", self.f.read(1))[0]
        if t == 1:   return struct.unpack("<b", self.f.read(1))[0]
        if t == 2:   return struct.unpack("<H", self.f.read(2))[0]
        if t == 3:   return struct.unpack("<h", self.f.read(2))[0]
        if t == 4:   return self.u32()
        if t == 5:   return struct.unpack("<i", self.f.read(4))[0]
        if t == 6:   return struct.unpack("<f", self.f.read(4))[0]
        if t == 7:   return struct.unpack("<?", self.f.read(1))[0]
        if t == 8:   return self.stringa()
        if t == 9:
            tt = self.u32()
            n = self.u64()
            return [self.valore(tt) for _ in range(n)]
        if t == 10:  return self.u64()
        if t == 11:  return struct.unpack("<q", self.f.read(8))[0]
        if t == 12:  return struct.unpack("<d", self.f.read(8))[0]
        raise ValueError("tipo kv sconosciuto %d" % t)


def leggi(path):
    with open(path, "rb") as f:
        r = Lettore(f)
        assert f.read(4) == b"GGUF", "non e' un GGUF: %s" % path
        r.u32()
        n_tensori = r.u64()
        n_kv = r.u64()
        kv = {}
        for _ in range(n_kv):
            k = r.stringa()
            kv[k] = r.valore(r.u32())
        tensori = []
        for _ in range(n_tensori):
            nome = r.stringa()
            nd = r.u32()
            dims = [r.u64() for _ in range(nd)]
            tipo = TIPI.get(r.u32(), "?")
            off = r.u64()
            tensori.append({"nome": nome, "dims": dims, "tipo": tipo, "offset": off})
        align = kv.get("general.alignment", 32)
        base = f.tell()
        base = (base + align - 1) // align * align
        return kv, tensori, base


def shard_di(primo, i):
    p = Path(primo)
    nome = p.name
    import re
    m = re.search(r"-(\d{5})-of-(\d{5})\.gguf$", nome)
    if not m:
        return p
    return p.with_name(nome[:m.start()] + "-%05d-of-%s.gguf" % (i, m.group(2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--elenca", action="store_true")
    ap.add_argument("--tensore")
    ap.add_argument("--esperti", type=int, default=48)
    ap.add_argument("--out")
    ap.add_argument("--json-out")
    a = ap.parse_args()

    import re
    m = re.search(r"-(\d{5})-of-(\d{5})\.gguf$", Path(a.gguf).name)
    n_shard = int(m.group(2)) if m else 1

    trovati = []
    for i in range(1, n_shard + 1):
        p = shard_di(a.gguf, i) if n_shard > 1 else Path(a.gguf)
        if not p.exists():
            continue
        kv, tensori, base = leggi(str(p))
        for t in tensori:
            t["shard"] = str(p)
            t["base"] = base
        trovati.extend(tensori)

    if a.elenca:
        vis = [t for t in trovati if "_exps" in t["nome"]]
        for t in vis[:40]:
            print("%-40s %-9s %s" % (t["nome"], t["tipo"], t["dims"]))
        conta = {}
        for t in trovati:
            if "_exps" in t["nome"]:
                conta[(t["tipo"], tuple(t["dims"]))] = conta.get((t["tipo"], tuple(t["dims"])), 0) + 1
        print("--- riepilogo esperti ---")
        for k, v in sorted(conta.items(), key=lambda x: -x[1]):
            print("%s dims=%s  x%d" % (k[0], list(k[1]), v))
        return

    scelto = next((t for t in trovati if t["nome"] == a.tensore), None)
    if scelto is None:
        raise SystemExit("tensore non trovato: %s" % a.tensore)
    npb, bpb = BLOCCHI[scelto["tipo"]]
    dims = scelto["dims"]           # [ne0, ne1, ne2] = [n_embd, n_ff_exp, n_expert]
    byte_per_esperto = dims[0] * dims[1] // npb * bpb
    n_e = min(a.esperti, dims[2] if len(dims) > 2 else 1)
    n_byte = byte_per_esperto * n_e
    with open(scelto["shard"], "rb") as f:
        f.seek(scelto["base"] + scelto["offset"])
        dati = f.read(n_byte)
    assert len(dati) == n_byte, "lettura corta"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_bytes(dati)
    meta = {"nome": scelto["nome"], "tipo": scelto["tipo"], "dims": dims,
            "shard": scelto["shard"], "byte_per_esperto": byte_per_esperto,
            "esperti_estratti": n_e, "byte_scritti": n_byte, "out": a.out}
    print(json.dumps(meta, indent=1))
    if a.json_out:
        Path(a.json_out).write_text(json.dumps(meta, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
