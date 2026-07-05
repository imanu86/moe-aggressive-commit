"""Track REAP-ds4 — costruisce il pacchetto prompt per la trace dominio sul pod.

Sorgente: bonus-kb raft_eval.jsonl (152 held-out Segnali, MAI committato in questo
repo). Output: runs/reap/<data>_trace_dominio/prompts/pNN.txt (GITIGNORED, solo
locale/scp) + manifest.json COMMITTATO (indici raft, sha256, lunghezze) cosi' ogni
numero derivato dalla trace cita una provenienza verificabile senza copiare la KB.

Selezione: 16 item stratificati (ogni 152/16-esimo) come prompt di estrazione
(system+user, decode = JSON gold ~150 tok) + 4 item lunghi trasformati in prompt
"spiega la strategia" (decode lungo 300-500 tok, use-case reale CGC Segnali).

Uso: python scripts/reap_build_trace_prompts.py [--date 2026-07-05]
"""
import argparse
import hashlib
import json
import os

RAFT = r"C:/Users/imanu/source/repos/bonus-kb/bonusx-kb/retrieval/ft/raft_eval.jsonl"
N_EXTRACT = 16
EXPLAIN_IDX = [7, 45, 91, 133]   # item con testo promo lungo, fissi per riproducibilita'
EXPLAIN_TMPL = ("Spiega passo passo, in italiano, la strategia ottimale per completare "
                "questa promo massimizzando il valore atteso, i rischi concreti e gli "
                "errori da evitare. Sii dettagliato.\n\n{promo}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-07-05")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(RAFT, encoding="utf-8")]
    base = os.path.join(os.path.dirname(__file__), "..", "runs", "reap",
                        f"{a.date}_trace_dominio")
    pdir = os.path.join(base, "prompts")
    os.makedirs(pdir, exist_ok=True)

    step = len(rows) // N_EXTRACT
    extract_idx = [i * step for i in range(N_EXTRACT)]
    manifest = {"source": "bonus-kb/bonusx-kb/retrieval/ft/raft_eval.jsonl",
                "source_sha256": hashlib.sha256(
                    open(RAFT, "rb").read()).hexdigest(),
                "n_raft_items": len(rows),
                "prompts": []}

    def emit(name, kind, raft_i, text, n_tokens):
        path = os.path.join(pdir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["prompts"].append({
            "file": name, "kind": kind, "raft_index": raft_i,
            "chars": len(text), "n_decode_target": n_tokens,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})

    for j, i in enumerate(extract_idx):
        m = rows[i]["messages"]
        text = m[0]["content"] + "\n\n" + m[1]["content"]
        emit(f"p{j:02d}_extract.txt", "extract", i, text, 320)
    for j, i in enumerate(EXPLAIN_IDX):
        promo = rows[i]["messages"][1]["content"]
        emit(f"p{16 + j:02d}_explain.txt", "explain", i,
             EXPLAIN_TMPL.format(promo=promo), 512)

    with open(os.path.join(base, "prompts_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    tot = sum(p["n_decode_target"] for p in manifest["prompts"])
    print(f"{len(manifest['prompts'])} prompt in {pdir}; decode target totale ~{tot} tok")
    print(f"manifest: {os.path.join(base, 'prompts_manifest.json')}")


if __name__ == "__main__":
    main()
