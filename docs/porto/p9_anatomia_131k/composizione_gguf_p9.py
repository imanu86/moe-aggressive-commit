"""P9 - legge SOLO l'intestazione dei tre shard del GGUF (metadati + elenco dei tensori:
i pesi non vengono toccati) e ne ricava i byte per categoria, cioe' il PAVIMENTO di byte
del decode a una riga.

Uso:
    python composizione_gguf_p9.py --gguf D:\\models\\...\\...-00001-of-00003.gguf --json-out log/p9_composizione.json
"""
import argparse
import json
import re
import struct
from collections import defaultdict
from pathlib import Path

# (nome, bit per peso, byte per blocco, pesi per blocco) - solo i tipi che servono
TIPI = {
    0: ("f32", 32), 1: ("f16", 16), 2: ("q4_0", 4.5), 3: ("q4_1", 5.0),
    6: ("q5_0", 5.5), 7: ("q5_1", 6.0), 8: ("q8_0", 8.5), 9: ("q8_1", 9.0),
    10: ("q2_k", 2.5625), 11: ("q3_k", 3.4375), 12: ("q4_k", 4.5), 13: ("q5_k", 5.5),
    14: ("q6_k", 6.5625), 15: ("q8_k", 8.0), 16: ("iq2_xxs", 2.0625), 17: ("iq2_xs", 2.3125),
    18: ("iq3_xxs", 3.0625), 19: ("iq1_s", 1.5625), 20: ("iq4_nl", 4.5), 21: ("iq3_s", 3.4375),
    22: ("iq2_s", 2.5), 23: ("iq4_xs", 4.25), 24: ("i8", 8), 25: ("i16", 16), 26: ("i32", 32),
    27: ("i64", 64), 28: ("f64", 64), 29: ("iq1_m", 1.75), 30: ("bf16", 16),
}

# dimensione dei blocchi: (pesi per blocco, byte per blocco)
BLOCCHI = {
    "f32": (1, 4), "f16": (1, 2), "bf16": (1, 2),
    "q4_0": (32, 18), "q4_1": (32, 20), "q5_0": (32, 22), "q5_1": (32, 24), "q8_0": (32, 34),
    "q2_k": (256, 84), "q3_k": (256, 110), "q4_k": (256, 144), "q5_k": (256, 176),
    "q6_k": (256, 210), "q8_k": (256, 292),
    "iq2_xxs": (256, 66), "iq2_xs": (256, 74), "iq2_s": (256, 82), "iq3_xxs": (256, 98),
    "iq3_s": (256, 110), "iq1_s": (256, 50), "iq1_m": (256, 56), "iq4_nl": (32, 18),
    "iq4_xs": (256, 136),
}


class Lettore:
    def __init__(self, f):
        self.f = f

    def u32(self):
        return struct.unpack("<I", self.f.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.f.read(8))[0]

    def i32(self):
        return struct.unpack("<i", self.f.read(4))[0]

    def stringa(self):
        n = self.u64()
        return self.f.read(n).decode("utf-8", errors="replace")

    def valore(self, t):
        if t == 0:   return struct.unpack("<B", self.f.read(1))[0]
        if t == 1:   return struct.unpack("<b", self.f.read(1))[0]
        if t == 2:   return struct.unpack("<H", self.f.read(2))[0]
        if t == 3:   return struct.unpack("<h", self.f.read(2))[0]
        if t == 4:   return self.u32()
        if t == 5:   return self.i32()
        if t == 6:   return struct.unpack("<f", self.f.read(4))[0]
        if t == 7:   return bool(struct.unpack("<B", self.f.read(1))[0])
        if t == 8:   return self.stringa()
        if t == 9:
            tt = self.u32()
            n = self.u64()
            return [self.valore(tt) for _ in range(n)]
        if t == 10:  return self.u64()
        if t == 11:  return struct.unpack("<q", self.f.read(8))[0]
        if t == 12:  return struct.unpack("<d", self.f.read(8))[0]
        raise ValueError("tipo kv sconosciuto %d" % t)


def leggi_intestazione(path):
    with open(path, "rb") as f:
        r = Lettore(f)
        assert f.read(4) == b"GGUF", "non e' un GGUF: %s" % path
        ver = r.u32()
        n_tensori = r.u64()
        n_kv = r.u64()
        kv = {}
        for _ in range(n_kv):
            k = r.stringa()
            t = r.u32()
            kv[k] = r.valore(t)
        tensori = []
        for _ in range(n_tensori):
            nome = r.stringa()
            nd = r.u32()
            dims = [r.u64() for _ in range(nd)]
            tipo = r.u32()
            off = r.u64()
            nomeq = TIPI.get(tipo, ("tipo%d" % tipo, None))[0]
            pesi = 1
            for d in dims:
                pesi *= d
            if nomeq in BLOCCHI:
                npb, bpb = BLOCCHI[nomeq]
                byte = pesi // npb * bpb
            else:
                byte = None
            tensori.append({"nome": nome, "dims": dims, "tipo": nomeq, "pesi": pesi,
                            "byte": byte, "offset": off})
        return {"versione": ver, "kv": kv, "tensori": tensori}


def categoria(nome):
    """Categoria d'uso nel decode a una riga."""
    if re.search(r"_exps", nome):
        if "ffn_down_exps" in nome:
            return "esperti_down"
        return "esperti_gate_up"
    if "per_layer_token_embd" in nome:
        return "ple_embedding_per_strato"
    if nome.startswith("token_embd"):
        return "embedding_token"
    if nome.startswith("output") or "output.weight" in nome:
        return "testa_output"
    if "ffn_gate_inp" in nome or "ffn_gate_inp_shexp" in nome or "exp_probs_b" in nome:
        return "router"
    if "shexp" in nome:
        return "esperto_condiviso"
    if re.search(r"attn|indexer|qsa", nome):
        return "attenzione_qsa"
    if re.search(r"ssm|conv1d|dt_|A_|D$|gdn|linear_attn", nome):
        return "gdn_ssm"
    if re.search(r"norm", nome):
        return "norme"
    return "altro"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True, help="primo shard")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    p0 = Path(args.gguf)
    m = re.match(r"(.*)-(\d{5})-of-(\d{5})\.gguf$", p0.name)
    shard = [p0]
    if m:
        tot = int(m.group(3))
        shard = [p0.with_name("%s-%05d-of-%05d.gguf" % (m.group(1), i, tot)) for i in range(1, tot + 1)]

    tutti = []
    kv0 = None
    for s in shard:
        h = leggi_intestazione(s)
        if kv0 is None:
            kv0 = h["kv"]
        tutti.extend(h["tensori"])

    per_cat = defaultdict(lambda: {"n": 0, "byte": 0, "pesi": 0, "tipi": defaultdict(int)})
    per_tipo = defaultdict(lambda: {"n": 0, "byte": 0})
    for t in tutti:
        c = categoria(t["nome"])
        per_cat[c]["n"] += 1
        per_cat[c]["byte"] += t["byte"] or 0
        per_cat[c]["pesi"] += t["pesi"]
        per_cat[c]["tipi"][t["tipo"]] += 1
        per_tipo[t["tipo"]]["n"] += 1
        per_tipo[t["tipo"]]["byte"] += t["byte"] or 0

    out = {
        "shard": [str(s) for s in shard],
        "n_tensori": len(tutti),
        "metadati": {k: v for k, v in kv0.items()
                     if isinstance(v, (int, float, str)) and not k.startswith("tokenizer")},
        "per_categoria": {k: {"n": v["n"], "byte": v["byte"],
                              "gib": round(v["byte"] / (1 << 30), 4),
                              "pesi": v["pesi"],
                              "bpw": round(v["byte"] * 8 / v["pesi"], 4) if v["pesi"] else None,
                              "tipi": dict(v["tipi"])}
                          for k, v in sorted(per_cat.items(), key=lambda x: -x[1]["byte"])},
        "per_tipo": {k: {"n": v["n"], "gib": round(v["byte"] / (1 << 30), 4)}
                     for k, v in sorted(per_tipo.items(), key=lambda x: -x[1]["byte"])},
        "tensori": [{"nome": t["nome"], "dims": t["dims"], "tipo": t["tipo"],
                     "pesi": t["pesi"], "byte": t["byte"]} for t in tutti],
        "tensori_di_un_blocco_campione": [
            {"nome": t["nome"], "dims": t["dims"], "tipo": t["tipo"], "byte": t["byte"]}
            for t in tutti if t["nome"].startswith("blk.5.") or t["nome"].startswith("blk.6.")],
        "tensori_fuori_blocco": [
            {"nome": t["nome"], "dims": t["dims"], "tipo": t["tipo"], "byte": t["byte"]}
            for t in tutti if not t["nome"].startswith("blk.")],
    }
    testo = json.dumps(out, indent=1, ensure_ascii=False)
    if args.json_out:
        Path(args.json_out).write_text(testo, encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_tensori", "per_categoria", "per_tipo")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
