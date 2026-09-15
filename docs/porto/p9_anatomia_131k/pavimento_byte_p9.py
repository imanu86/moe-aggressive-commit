"""P9 - pavimento di byte del decode a UNA riga, per categoria.

Da `log/p9_composizione.json` (intestazioni dei tre shard del GGUF) ricava i byte che
il decode di un token deve leggere, e li divide per la banda MISURATA sulla macchina
(`log/p9_banda_microbanco.txt`) per ottenere il tempo minimo di ogni categoria.

Regole dichiarate (sono ipotesi, non misure):
  - a batch 1 ogni matvec legge la matrice INTERA una volta: byte = byte del tensore;
  - i tensori f32 di forma [n] (norme, bias) e i tensori `*_inject` sono contati lo
    stesso, sono pochi byte;
  - `token_embd` e `per_layer_token_embd` sono letti per RIGA, non per intero:
    contati come poche centinaia di byte, cioe' zero;
  - gli esperti: 10 instradati su 512, per ognuno dei 48 strati, gate+up+down;
  - la quota di esperti che arriva dal PCIe e' un parametro (`--esperti-mancanti`),
    di default 3 su 10 per strato, cioe' il 30%, coerente con i 271 MiB per forward
    contati da nsys il 14/9 e con il 75,5% di colpi caldi del simulatore;
  - KV e indicizzatore stanno in memoria host mappata (`QWEN4EXP_ATTN_MAPPED=1`,
    `QWEN4EXP_INDEXER_MAPPED=1`): i loro byte passano dal bus, non dalla VRAM.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# banda misurata il 15/9 con banda_zerocopy.exe (log/p9_banda_microbanco.txt)
BANDA_VRAM_GBS = 340.3      # lettura da VRAM, media di 3 ripetizioni
BANDA_PCIE_GBS = 26.3       # zero-copy GPU e DMA H2D danno lo stesso numero
BANDA_RAM_CPU_GBS = 33.4    # lettura CPU a 16 thread, per confronto

STRATI_ATTN = {3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47}


def categoria_densa(nome_corto, blk):
    """Categoria d'uso a decode, per i tensori NON esperti."""
    if nome_corto.startswith("ffn_gate_inp.weight"):
        return "router_f32"
    if "shexp" in nome_corto:
        return "esperto_condiviso"
    if nome_corto.startswith("hc_"):
        return "connessioni_hc"
    if nome_corto.startswith("ssm") or nome_corto.startswith("attn_gate") or \
            (nome_corto.startswith("attn_qkv") and blk not in STRATI_ATTN):
        return "gdn_ssm"
    if nome_corto.startswith("indexer"):
        return "indexer_qsa_pesi"
    if nome_corto.startswith("attn_"):
        return "attenzione_qsa"
    if nome_corto.startswith("ple_"):
        return "ple_ngram"
    return "altro_denso"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--composizione", default=str(HERE / "log" / "p9_composizione.json"))
    ap.add_argument("--esperti-mancanti", type=float, default=3.0,
                    help="esperti per strato che NON sono in cache e arrivano dal PCIe")
    ap.add_argument("--n-kv", type=int, default=131248, help="profondita' del contesto")
    ap.add_argument("--indexer-top-k", type=int, default=2048)
    ap.add_argument("--json-out", default=str(HERE / "log" / "p9_pavimento.json"))
    args = ap.parse_args()

    d = json.loads(Path(args.composizione).read_text(encoding="utf-8"))
    T = d["tensori"]

    cat = defaultdict(lambda: {"byte": 0, "n": 0, "tipi": defaultdict(int)})
    esperti_per_strato = defaultdict(int)  # byte di UN esperto, per strato

    for t in T:
        m = re.match(r"blk\.(\d+)\.(.*)", t["nome"])
        if not m:
            if t["nome"].startswith("token_embd"):
                continue                      # letto per riga
            if t["nome"].startswith("per_layer_token_embd"):
                continue                      # letto per riga, e sta sulla CPU
            c = "testa_output"
        else:
            blk = int(m.group(1))
            corto = m.group(2)
            if "_exps" in corto:
                # 512 esperti nel tensore, se ne leggono 10
                esperti_per_strato[blk] += t["byte"] // 512
                continue
            if corto.startswith("per_layer") or corto.startswith("ple_"):
                continue                      # per riga
            c = categoria_densa(corto, blk)
        cat[c]["byte"] += t["byte"]
        cat[c]["n"] += 1
        cat[c]["tipi"][t["tipo"]] += 1

    n_strati = len(esperti_per_strato)
    byte_esperto_medio = sum(esperti_per_strato.values()) / n_strati
    esperti_totali = sum(v * 10 for v in esperti_per_strato.values())
    esperti_pcie = sum(v * args.esperti_mancanti for v in esperti_per_strato.values())
    esperti_vram = esperti_totali - esperti_pcie

    # KV e indicizzatore, dalla memoria host mappata
    # indicizzatore: top_k celle x (chiave 128 dim q8_0 = 136 B) x 12 strati
    idx_byte = args.indexer_top_k * 136 * 12
    # attenzione: le top_k celle scelte, K e V, 2 teste kv x 256 dim, q8_0 (8.5 bit)
    kv_byte = args.indexer_top_k * 2 * (256 + 256) * 17 // 16 * 12
    # bias per-cella della QSA: n_kv float per forward, copiati H2D (misurato da P7)
    bias_byte = args.n_kv * 4

    righe = []

    def riga(nome, byte, banda, nota):
        righe.append({"categoria": nome, "byte": int(byte), "mib": round(byte / (1 << 20), 2),
                      "banda_gbs": banda, "pavimento_ms": round(byte / (banda * 1e9) * 1e3, 3),
                      "nota": nota})

    riga("esperti — letti dalla cache in VRAM", esperti_vram, BANDA_VRAM_GBS,
         "%.0f%% dei 10 instradati x 48 strati" % (100 * (10 - args.esperti_mancanti) / 10))
    riga("esperti — caricati dal PCIe (gather)", esperti_pcie, BANDA_PCIE_GBS,
         "%.1f esperti mancanti per strato" % args.esperti_mancanti)
    for nome, chiave in [("attenzione QSA (q/k/v/o, q6_k+q8_0)", "attenzione_qsa"),
                         ("GDN/SSM (qkv, gate, out, q6_k+f32)", "gdn_ssm"),
                         ("connessioni HC (q8_0)", "connessioni_hc"),
                         ("router ffn_gate_inp (f32!)", "router_f32"),
                         ("esperto condiviso", "esperto_condiviso"),
                         ("pesi dell'indicizzatore QSA", "indexer_qsa_pesi"),
                         ("testa di uscita (q6_k)", "testa_output"),
                         ("altro denso", "altro_denso"),
                         ("PLE n-gram", "ple_ngram")]:
        if chiave in cat and cat[chiave]["byte"]:
            riga(nome, cat[chiave]["byte"], BANDA_VRAM_GBS,
                 "%d tensori, %s" % (cat[chiave]["n"], dict(cat[chiave]["tipi"])))
    riga("indicizzatore: gather di %d celle (host mappato)" % args.indexer_top_k,
         idx_byte, BANDA_PCIE_GBS, "136 B/cella x 12 strati")
    riga("KV delle celle scelte (host mappato)", kv_byte, BANDA_PCIE_GBS,
         "K+V 2x256 q8_0 x %d celle x 12 strati" % args.indexer_top_k)
    riga("bias QSA, copia H2D", bias_byte, BANDA_PCIE_GBS, "n_kv float per forward")

    tot_v = sum(r["pavimento_ms"] for r in righe if r["banda_gbs"] == BANDA_VRAM_GBS)
    tot_p = sum(r["pavimento_ms"] for r in righe if r["banda_gbs"] == BANDA_PCIE_GBS)
    byte_v = sum(r["byte"] for r in righe if r["banda_gbs"] == BANDA_VRAM_GBS)
    byte_p = sum(r["byte"] for r in righe if r["banda_gbs"] == BANDA_PCIE_GBS)

    out = {"parametri": {"esperti_mancanti_per_strato": args.esperti_mancanti,
                         "n_kv": args.n_kv, "indexer_top_k": args.indexer_top_k,
                         "banda_vram_gbs": BANDA_VRAM_GBS, "banda_pcie_gbs": BANDA_PCIE_GBS,
                         "banda_ram_cpu_gbs": BANDA_RAM_CPU_GBS},
           "byte_di_un_esperto_medio": int(byte_esperto_medio),
           "n_strati_moe": n_strati,
           "righe": righe,
           "totali": {"vram_byte": byte_v, "vram_mib": round(byte_v / (1 << 20), 1),
                      "vram_pavimento_ms": round(tot_v, 3),
                      "pcie_byte": byte_p, "pcie_mib": round(byte_p / (1 << 20), 1),
                      "pcie_pavimento_ms": round(tot_p, 3),
                      "somma_pavimento_ms": round(tot_v + tot_p, 3),
                      "pavimento_se_seriale_ms": round(tot_v + tot_p, 3),
                      "pavimento_se_sovrapposti_ms": round(max(tot_v, tot_p), 3)}}
    Path(args.json_out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

    print("%-46s %12s %10s %10s" % ("categoria", "MiB/token", "banda", "pavim. ms"))
    for r in righe:
        print("%-46s %12.2f %9.1f %10.3f" % (r["categoria"], r["mib"], r["banda_gbs"], r["pavimento_ms"]))
    print("-" * 82)
    print("%-46s %12.1f %9.1f %10.3f" % ("TOTALE VRAM", byte_v / (1 << 20), BANDA_VRAM_GBS, tot_v))
    print("%-46s %12.1f %9.1f %10.3f" % ("TOTALE PCIe", byte_p / (1 << 20), BANDA_PCIE_GBS, tot_p))
    print("%-46s %12.1f %9s %10.3f" % ("SOMMA (seriale)", (byte_v + byte_p) / (1 << 20), "-", tot_v + tot_p))
    print("%-46s %12s %9s %10.3f" % ("PAVIMENTO se le due corsie si sovrappongono", "-", "-", max(tot_v, tot_p)))


if __name__ == "__main__":
    main()
