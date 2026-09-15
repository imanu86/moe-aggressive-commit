"""P11 cella 2 - genera i preset X0..X3 dal candidato W4.

X0 = controllo: stessi binari ricompilati delle celle X, ma A1 SPENTA. Serve a
     separare "quanto vale A1" da "quanto vale la build" (regola dell'8/9: dopo una
     build la macchina non e' quieta, fino al 15%). Senza X0 il confronto con W4
     sarebbe fra binari diversi, l'errore dichiarato della cella W5.
X1 = W4 + A1, batch/ubatch 3072.
X2 = W4 + A1, batch/ubatch 4096.
X3 = X2 + scaletta dell'ubatch (leva W5), ricalcolata sulla nuova workspace.

Scrive docs/porto/banco_p0/preset_X<n>_p11.json in UTF-8 SENZA BOM.
"""
import json
from pathlib import Path

BANCO = Path(__file__).resolve().parent.parent / "banco_p0"
BIN_NUOVI = "D:\\ds4_work\\p11_work\\build\\bin"

A1 = ("A1 (P11 cella 2) = le tre maschere F32 [n_kv, n_batch] dell'indicizzatore QSA "
      "non si materializzano piu' intere: la selezione top-k si calcola a fette di "
      "QWEN4EXP_QSA_TOPK_CHUNK token (512), e la seconda maschera F16 di build_attn_qsa "
      "diventa una somma in posto (QWEN4EXP_QSA_MASK_INPLACE). Stessi valori, stesso "
      "kernel: cambia solo quanta workspace vive insieme.")

DEV = ("binari RICOMPILATI in " + BIN_NUOVI + " dall'albero delle celle W0-W4 piu' "
       "p11.patch (ubatch a scaletta) piu' p11_cella2.patch (A1). Il controllo a "
       "binario invariato e' la cella X0, che gira sugli STESSI binari con A1 spenta.")


def imposta_arg(args, chiave, valore):
    a = list(args)
    for i, v in enumerate(a):
        if v == chiave:
            a[i + 1] = valore
            return a
    raise SystemExit("argomento %s non trovato" % chiave)


def scrivi(base, ident, etichetta, descrizione, differenze, env, batch=None, ubatch=None):
    p = json.loads((BANCO / base).read_text(encoding="utf-8"))
    p["id"] = ident
    p["etichetta"] = etichetta
    p["descrizione"] = descrizione
    p["differenze_da_V3"] = differenze
    p["derivato_da"] = base
    p["binari"] = BIN_NUOVI
    dev = [d for d in p["deviazioni_dal_lanciatore_quotidiano"] if not d.startswith("binari")]
    dev.append(DEV)
    p["deviazioni_dal_lanciatore_quotidiano"] = dev
    for k, v in env.items():
        if v is None:
            p["env"].pop(k, None)
        else:
            p["env"][k] = v
    if batch:
        p["args"] = imposta_arg(p["args"], "-b", batch)
    if ubatch:
        p["args"] = imposta_arg(p["args"], "-ub", ubatch)
    out = BANCO / ("preset_%s_p11.json" % ident)
    out.write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("scritto %s" % out)


COMUNE = ("Punto operativo P11: prefill FREDDO di 131.072 token (profilo prefill_131k), "
          "MTP spento, 64 slot, KV 262144, greedy seed 1234, ragionamento acceso, "
          "risposta brevissima (64 token). ")

scrivi("preset_W4_p11.json", "X0", "p11_x0_controllo_binari_nuovi",
       COMUNE + "X0 = W4 esatta (sparse FA + batch 3072 + GDN a tile + staging) sui "
       "binari NUOVI con A1 SPENTA. Non e' un candidato: e' il controllo che dice "
       "quanto della differenza con W4 e' della build e quanto di A1.",
       "come W4, ma binari ricompilati e A1 dichiarata spenta.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "0", "QWEN4EXP_QSA_MASK_INPLACE": "0",
        "QWEN_WS_DUMP": "25"})

scrivi("preset_W4_p11.json", "X1", "p11_x1_a1_batch3072",
       COMUNE + "X1 = W4 + A1 a batch/ubatch 3072. " + A1 +
       " Attesa: workspace molto piu' bassa e staging degli esperti acceso fino in "
       "fondo, invece di spegnersi negli ultimi 13 blocchi su 44.",
       "sparse FA + batch 3072 + GDN a tile + staging (da W4) + A1.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "512", "QWEN4EXP_QSA_MASK_INPLACE": "1"})

scrivi("preset_W4_p11.json", "X2", "p11_x2_a1_batch4096",
       COMUNE + "X2 = W4 + A1 a batch/ubatch 4096. " + A1 +
       " Il batch 4096 a 131k era crollato del 40,7% (cella W2) per paginazione WDDM: "
       "workspace 8942 MiB e VRAM libera 507 MiB. Fino a kv 115k pero' leggeva a 463 "
       "t/s cumulativi. A1 toglie il termine token x cella dalla workspace: se il muro "
       "era di memoria e non di aritmetica, qui non deve piu' esserci.",
       "sparse FA + GDN a tile + staging (da W4) + A1, batch/ubatch da 3072 a 4096.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "512", "QWEN4EXP_QSA_MASK_INPLACE": "1",
        "QWEN_WS_DUMP": "25"},
       batch="4096", ubatch="4096")

# X3 - la scaletta dell'ubatch RICALCOLATA sul fabbisogno dello staging, non sul tetto
# della VRAM. E' l'errore di progetto dichiarato in P11 §7.3. A1 resta SPENTA: le celle
# X1/X2 hanno mostrato che non paga. Il conto, sui punti misurati:
#   ws(T,K) ~ const(T) + pendenza(T)*K   [MiB]
#   const/pendenza:  2048 -> 1098 / 0,02245   3072 -> 1115 / 0,03868   4096 -> 1619 / 0,04967
# In W4/X0, a workspace 6819 MiB la VRAM libera era 400: il tetto "workspace + libera"
# vale ~7220 MiB. Lo staging pretende ~1,4 GiB liberi, cioe' workspace <= ~5800 MiB.
#   riserve fino a kv  65536 -> 4096  (ws max 4875, libera ~2,3 GiB)
#   riserve  81920 e  98304 -> 3072  (ws max 4917, libera ~2,3 GiB)
#   riserve da 114688 in su -> 2048  (ws max 4408, libera ~2,8 GiB)
scrivi("preset_W4_p11.json", "X3", "p11_x3_scaletta_per_staging",
       COMUNE + "X3 = W4 + scaletta dell'ubatch calcolata perche' la VRAM libera non "
       "scenda MAI sotto il fabbisogno dello staging (~1,4 GiB), invece che sul solo "
       "tetto della VRAM come in W5. Batch/ubatch 4096 fino a kv 65536, 3072 a 81920 e "
       "98304, 2048 da 114688. A1 spenta. Attesa: staging attivo in tutti i blocchi, "
       "compresi gli ultimi 13 dove in W4 si spegneva e i tempi tornavano quelli senza.",
       "sparse FA + GDN a tile + staging (da W4), -b/-ub 4096 e "
       "QWEN_PREFILL_UBATCH_DEEP=81920:3072,114688:2048.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "0", "QWEN4EXP_QSA_MASK_INPLACE": "0",
        "QWEN_PREFILL_UBATCH_DEEP": "81920:3072,114688:2048"},
       batch="4096", ubatch="4096")

# X4 - X3 con il BATCH che si divide per ogni gradino della scaletta.
# In X3 il server manda blocchi da 4096 e la scaletta li spezza in ubatch da 3072:
# 4096 = 3072 + 1024, cioe' un ubatch pieno e uno lungo un terzo. I due tratti a 3072
# costano 45,0 e 47,5 s contro i 38,5 e 40,7 della cella X0, che a 3072 ha il batch
# giusto: +17%, tredici secondi su 337. Con -b 12288 (= 3x4096 = 4x3072 = 6x2048) ogni
# gradino divide il blocco esattamente. L'ubatch resta 4096: -b non entra nel grafo.
scrivi("preset_W4_p11.json", "X4", "p11_x4_scaletta_batch_divisibile",
       COMUNE + "X4 = X3 con -b 12288, cioe' un blocco che si divide esattamente per "
       "ogni gradino della scaletta (12288 = 3x4096 = 4x3072 = 6x2048). In X3 i due "
       "tratti a ubatch 3072 pagavano uno split irregolare 3072+1024. -ub resta 4096 e "
       "la scaletta e' la stessa: la workspace non cambia, cambia solo come il blocco "
       "viene tagliato.",
       "sparse FA + GDN a tile + staging (da W4), -ub 4096, -b 12288 e "
       "QWEN_PREFILL_UBATCH_DEEP=81920:3072,114688:2048.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "0", "QWEN4EXP_QSA_MASK_INPLACE": "0",
        "QWEN_PREFILL_UBATCH_DEEP": "81920:3072,114688:2048"},
       batch="12288", ubatch="4096")

# X5 - un gradino in piu' in cima. Il costo per token non e' solo attenzione: ogni BLOCCO
# di prompt trasferisce gli stessi 45,4 GiB di pesi degli esperti, quindi l'ubatch grande
# paga due volte (meno blocchi = meno traffico sul bus). Dove la VRAM abbonda - e con la
# scaletta ne avanza 1,65 GiB - conviene salire. 12288 = 2x6144, quindi il blocco resta
# divisibile su tutti e quattro i gradini.
#   riserve fino a kv  49152 -> 6144 (ws stimata 5506 max, libera ~1,7 GiB)
#   riserve  65536 e  81920 -> 4096 (ws 5689 max, libera ~1,5 GiB)
#   riserve  98304 e 114688 -> 3072 (ws 5551 max, libera ~1,7 GiB)
#   riserve da 131072 in su -> 2048 (ws 4408 max, libera ~2,8 GiB)
scrivi("preset_W4_p11.json", "X5", "p11_x5_scaletta_da_6144",
       COMUNE + "X5 = X4 con un gradino in piu' in cima: -ub 6144 fino a kv 49152, poi "
       "4096, 3072 e 2048. -b resta 12288, che si divide per tutti e quattro. L'ipotesi "
       "e' che nella prima fascia il collo non sia l'attenzione ma il traffico degli "
       "esperti, che scala con il NUMERO DI BLOCCHI: da 4 blocchi per tratto a 2,67.",
       "sparse FA + GDN a tile + staging (da W4), -ub 6144, -b 12288 e "
       "QWEN_PREFILL_UBATCH_DEEP=65536:4096,98304:3072,131072:2048.",
       {"QWEN4EXP_QSA_TOPK_CHUNK": "0", "QWEN4EXP_QSA_MASK_INPLACE": "0",
        "QWEN_PREFILL_UBATCH_DEEP": "65536:4096,98304:3072,131072:2048"},
       batch="12288", ubatch="6144")
