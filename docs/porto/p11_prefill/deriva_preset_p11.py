"""P11 - deriva un preset dal candidato precedente aggiungendo UNA manopola.

Uso:
  python deriva_preset_p11.py --base preset_W1_p11.json --id W3 \
      --etichetta p11_w3_gdn_tile --env QWEN_GDN_TILED=1 \
      --descrizione "..." --differenze "..." [--batch 4096] [--ubatch 2048]

Scrive docs/porto/banco_p0/preset_<ID>_p11.json in UTF-8 senza BOM.
"""
import argparse
import json
from pathlib import Path

BANCO = Path(__file__).resolve().parent.parent / "banco_p0"


def imposta_arg(args, chiave, valore):
    a = list(args)
    for i, v in enumerate(a):
        if v == chiave:
            a[i + 1] = valore
            return a
    raise SystemExit("argomento %s non trovato" % chiave)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--etichetta", required=True)
    ap.add_argument("--descrizione", default="")
    ap.add_argument("--differenze", default="")
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--batch", default=None)
    ap.add_argument("--ubatch", default=None)
    a = ap.parse_args()

    base_path = BANCO / a.base if not Path(a.base).is_absolute() else Path(a.base)
    p = json.loads(base_path.read_text(encoding="utf-8"))
    p["id"] = a.id
    p["etichetta"] = a.etichetta
    if a.descrizione:
        p["descrizione"] = a.descrizione
    p["differenze_da_V3"] = a.differenze or p.get("differenze_da_V3")
    p["derivato_da"] = base_path.name
    for e in a.env:
        k, _, v = e.partition("=")
        p["env"][k] = v
    if a.batch:
        p["args"] = imposta_arg(p["args"], "-b", a.batch)
    if a.ubatch:
        p["args"] = imposta_arg(p["args"], "-ub", a.ubatch)
    out = BANCO / ("preset_%s_p11.json" % a.id)
    out.write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("scritto %s" % out)


if __name__ == "__main__":
    main()
