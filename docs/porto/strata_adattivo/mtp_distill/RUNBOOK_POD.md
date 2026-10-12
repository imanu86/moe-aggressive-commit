# Runbook del pod — distillazione del layer MTP di Qwen3.8-Flash-Next (Strata)

Obiettivo: catturare sul tronco IQ3_XXS di produzione i residui finali e i top-20 del target su ~3,5M token delle
conversazioni dell'owner (bonificate), affinare il layer MTP (KL top-20 srotolata su 4 passi, #97), esportare il pacco
`rt_it48k_ft1` nel formato del motore e misurarne l'accettazione contro `rt_it48k`.  Tutto in un giorno di noleggio.

Stato dei pezzi: vedi `README.md` (cosa è provato in locale e cosa no).  **Il noleggio lo avvia il coordinatore dopo la
conferma dell'owner sul costo**: qui solo i comandi, nessuno crea pod.

## 1. Pod consigliato

| | Scelta | Perché |
|---|---|---|
| GPU | **1× H100 SXM 80 GB** (Secure Cloud) — in alternativa 1× H200 141 GB se costa quasi uguale | Il pacco IQ3_XXS vuole ~43 GB di arena esperti + ~5 GB densi + testa/embedding + K/V a 4k: tutto in VRAM su 80 GB. Il training vuole ~25-35 GB (esperti bf16 5 GB, embedding+testa 2,5 GB, attivazioni della catena a 4096). Cattura e training sono in sequenza: una scheda basta. |
| vCPU / RAM | ≥ 16 vCPU, ≥ 128 GB RAM | setup.py stima 60 GB di RAM per IQ3_XXS (l'arena vive anche in RAM); il thread della cattura fa top-k su 248k logit per riga. |
| Disco | **container disk 300 GB** (NVMe locale) per shard GGUF (76 GB), pack, catture (~72 GB in bf16), checkpoint; network volume **facoltativo** (200 GB) solo per tenere le catture dopo il pod | Il PLE (`per_layer_token_embd`, 28,8 GB) è letto a righe per token dal secondo shard: deve stare su disco locale, non su un volume di rete. |
| Immagine | `runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04` (ha nvcc 12.8, torch) — oppure `nvidia/cuda:13.0.0-devel-ubuntu24.04` + pip torch | Strata compila con CUDA 12.x o 13 (CMake rifiuta solo < sm_75; H100 = sm_90). |
| Porte / SSH | SSH con chiave (`runpodctl ssh`), niente porte pubbliche | Il motore ascolta solo su stdin (`--serve`), nessun server HTTP serve. |

Costo indicativo (da confermare sulla console al momento): H100 SXM 80 GB ≈ 2,7–3,0 $/h, H200 ≈ 3,6–4,0 $/h,
disco container ≈ 0,10 $/GB-mese, volume di rete ≈ 0,07 $/GB-mese.  **Stima dell'intero lavoro: 6–8 h → 18–30 $ su H100
(25–40 $ su H200); un giorno intero di margine resta sotto i 100 $.**

Comandi `runpodctl` (sola lettura ora; la creazione la fa il coordinatore):

```
runpodctl gpu list                       # tipi e disponibilità (senza prezzi: vedere la console)
runpodctl datacenter list                # dove c'è stock di H100/H200
runpodctl pod create --help              # i flag della versione installata (2.6.1)
# esempio (NON eseguito): runpodctl pod create --name mtp-distill --gpu "NVIDIA H100 80GB HBM3" --gpu-count 1 \
#   --image runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04 --container-disk 300 --volume-size 0 --ssh
runpodctl pod list ; runpodctl ssh connect <pod>
```

## 2. Setup sul pod (≈ 35–50 min, in parallelo dove possibile)

```bash
# 2.1 dipendenze (2 min)
apt-get update && apt-get install -y build-essential cmake ninja-build git git-lfs python3-venv libgomp1 zstd
pip install numpy safetensors jinja2 regex gguf zstandard   # torch c'è nell'immagine; altrimenti pip install torch

# 2.2 il fork, branch con l'hook di cattura (il fork imanu86/Strata-2080Ti è pubblico; altrimenti runpodctl send di uno zip)
cd /workspace && git clone -b lab/mtp-capture https://github.com/imanu86/Strata-2080Ti.git strata && cd strata
git log --oneline -1       # deve essere 6e5b24f6 (o successivo) "FABLE-MTP-Aggiungi la cattura opt-in STRATA_MTP_CAPTURE"

# 2.3 modello: i due shard GGUF da Hugging Face (76 GB; sul pod 2-15 min, molto più veloce che caricarli dal PC)
mkdir -p /workspace/gguf && cd /workspace/gguf
# repo e revisione fissati in setup.py (HF_REVISIONS): ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF @ ed59f920
pip install -U huggingface_hub && hf download ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF \
   --revision ed59f92082b1e93c0e96d60a8b11aab089b52f09 --include "*IQ3_XXS*" --local-dir /workspace/gguf
ls -la /workspace/gguf   # Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf (47,0 GB) e -00002- (28,8 GB)

# 2.4 motore + pack con setup (compila per sm_90 ~15-25 min; prepara il pack dal GGUF; non avvia il server)
cd /workspace/strata && ./setup.sh --gguf-dir /workspace/gguf --model IQ3_XXS --context 32768 --kv int8 \
   --vision no --build --no-start --yes --data-dir /workspace/Strata-data
#   -> motore in build/strata (o engine/), config in /workspace/strata/strata-iq3_xxs.json (args, cwd, lib_dirs, env)
#   Il pack (1,5 GB: dense.bin, index, native_experts.txt, tokenizer) si può anche copiare dal PC
#   (D:\ds4_work\strata\Strata-data\packs\iq3_xxs, stessi file HF) per saltare la verifica bit-a-bit del pack.
```

Trasferimenti dal PC (`runpodctl send <file>` → sul pod `runpodctl receive <code>`; oppure `scp` via la connessione SSH):

| Cosa | Da | Dimensione | Tempo a 100 Mbit/s (a 1 Gbit/s) |
|---|---|---|---|
| sequenze del corpus | `D:\ds4_work\mtp_distill\seqs\` (seqs_ids.i32, seqs_gen.u8, seqs_index.json, render_stats.json) | 18 MB | secondi |
| blocco MTP BF16 **denso** | `D:\ds4_work\strata\Strata-data\mtp\{mtp-manifest.json, tensors\mtp.*.bin}` SENZA i due `experts` | 190 MB | 15 s (2 s) |
| pacco in uso | `D:\ds4_work\strata\Strata-data\mtp\rt_it48k\` (experts.bin 708 MB, dense.bin 116 MB, dense.txt, draft_vocab.bin) | 824 MB | 70 s (7 s) |
| codice | `mtp_distill/*.py` (questa cartella; `git clone` del lab o `runpodctl send`) | < 1 MB | — |
| (facoltativo) pack preparato | `D:\ds4_work\strata\Strata-data\packs\iq3_xxs\` | 1,5 GB | 2 min (12 s) |

I due file `tensors\mtp.layers.0.mlp.experts.*.bin` (5 GB) NON servono: gli esperti instradati sono congelati e il
training usa quelli Q2_0 di `rt_it48k/experts.bin`, che il motore esegue (`--experts q2`, default).

Variabili usate sotto:
```bash
export S=/workspace/strata  CFG=$S/strata-iq3_xxs.json  EXE=$S/build/strata   # EXE: quello che la config indica in "exe"
export D=/workspace/mtp_distill   # seqs/, bf16/, rt_it48k/, capture/, runs/
export CODE=/workspace/mtp_distill/code  # i .py di questa cartella
python3 -c "import json;print(json.load(open('$CFG'))['exe'])"   # il percorso vero del motore compilato
```

## 3. Cattura del target (≈ 2–3,5 h per 3,5M token)

Prova di ritmo (3 min) e poi tutto:
```bash
cd $D && python3 $CODE/capture_driver.py --exe $EXE --config $CFG --seqs $D/seqs --out $D/capture --count 30
#   stampa tok/s: con ~400 tok/s 3,5M token sono ~2,5 h; sotto 150 tok/s fermarsi e guardare il log del motore
nohup python3 $CODE/capture_driver.py --exe $EXE --config $CFG --seqs $D/seqs --out $D/capture > $D/capture.log 2>&1 &
tail -f $D/capture.log     # "N/1197 sequenze, T token, tok/s"; capture_map.json aggiorna ogni 20 sequenze
```
Cosa fa: avvia `strata --serve` con gli argomenti della config meno `--mtp`/cache/spec, più
`--short-read 1000000000 --prompt-cache 0 --spec 8` e `STRATA_MTP_CAPTURE=$D/capture/run_<ts>`; ogni sequenza è una
`GEN 1 ckpt=0 <ids>`: il prompt passa tutto dalle finestre di verifica teacher-forced (8 righe) e l'hook scrive per
posizione il residuo finale (bf16, 20 KB) e i top-20.  Una ripresa (`Ctrl-C`, pod riavviato) salta le sequenze già
buone e apre un nuovo `run_`.  Disco: ~20,2 KB/token → 72 GB per 3,5M token.

Controlli: `ls $D/capture/run_*/ | head`; `python3 -c "import json;m=json.load(open('$D/capture/capture_map.json'));print(sum(v['ok'] for v in m.values()),'ok su',len(m))"`.
Se la cattura è più lenta del previsto, si può tagliare il corpus (`--count 800` ≈ 2,3M token) e partire col training.

## 4. Training (≈ 40–90 min per 2 epoche)

```bash
mkdir -p $D/runs && cd $D && nohup python3 $CODE/train_mtp.py --bf16 $D/bf16 --rt $D/rt_it48k \
  --gguf /workspace/gguf/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_XXS-00001-of-00002.gguf --strata $S \
  --seqs $D/seqs --capture $D/capture --out $D/runs/ft1 --steps 4 --epochs 2 --lr 3e-5 --accum 4 \
  --eval-every 100 --eval-items 36 > $D/runs/ft1.log 2>&1 &
tail -f $D/runs/ft1.log
```
- La prima riga di eval (`eval iniziale`) è l'accettazione del layer **attuale** sui dati dell'owner, per passo
  (`acc`), con la quota di bozze offerte a `--spec-min-p 0.5` e la lunghezza media della catena accettata: è il numero
  da battere (il Daily misura 65-70 %, 1,7-2,0 token/finestra).
- Riferimenti #97 (stesso modello, BF16): 0,88/0,75/0,64/0,53 → 0,91/0,80/0,70/0,61.  Se dopo 1 epoca `acc` del passo 0
  non sale di almeno 1 punto, provare `--lr 6e-5` oppure `--no-train-fc` (perimetro di #97); se cala, `--lr 1e-5`.
- Varianti: `--step-weights 1,0.8,0.6,0.5`; `--full-head` (KL su tutto il vocabolario: più lento, più fedele ma il
  motore propone solo il sottoinsieme); `--hnorm-stream` solo se il Daily usasse `--mtp-hnorm stream` (non lo usa).
- Uscite: `runs/ft1/trainable.safetensors` (pesi affinati, nomi corti), `log.jsonl`, `eval.json`.

## 5. Export e verifica sul motore (≈ 15 min)

```bash
python3 $CODE/export_mtp.py --bf16 $D/bf16 --rt $D/rt_it48k --weights $D/runs/ft1/trainable.safetensors --out $D/rt_it48k_ft1
#   stampa per tensore quanto si è mosso e l'errore Q8_0; experts.bin e draft_vocab.bin sono copiati da rt_it48k
# controllo del percorso (deve dire IDENTICO x3): export del blocco originale contro il pacco in uso
python3 $CODE/export_mtp.py --bf16 $D/bf16 --rt $D/rt_it48k --out /tmp/rt_identity --check-against $D/rt_it48k
# il motore col pacco nuovo contro quello vecchio, stessi prompt heldout, greedy
python3 $CODE/bench_pack.py --exe $EXE --config $CFG --seqs $D/seqs --mtp $D/rt_it48k --mtp $D/rt_it48k_ft1 --n 24 --prompt-tokens 1024 --max-new 256
#   per pacco: accepted/offered, token per finestra, t/s; le uscite devono essere identiche (greedy: il drafter non cambia il testo)
```
Il pacco nuovo si carica col motore invariato: `--mtp $D/rt_it48k_ft1` (stesso layout di `rt_it48k`).

## 6. Cosa riportare a casa (prima di cancellare il pod)

| Cosa | Dimensione | Dove sul PC |
|---|---|---|
| `rt_it48k_ft1/` (dense.bin, dense.txt, experts.bin, draft_vocab.bin, export_report.json) | 824 MB | `D:\ds4_work\strata\Strata-data\mtp\rt_it48k_ft1\` |
| `runs/ft1/trainable.safetensors`, `log.jsonl`, `eval.json` | 360 MB | `D:\ds4_work\mtp_distill\runs\ft1\` |
| `bench_pack.json`, `capture.log`, `ft1.log`, il log del motore della cattura | < 10 MB | `docs/porto/strata_adattivo/mtp_distill/esiti/` (nel lab, solo i json/log: niente dati) |
| (facoltativo) le catture `capture/` | 72 GB | non servono a casa; o un network volume (≈ 5 $/mese) per un secondo giro |

`runpodctl send` dal pod o `scp` dal PC.  Poi: **`runpodctl pod stop <id>` e `runpodctl pod remove <id>`** (uno stop
lascia il disco a pagamento).  Il pod viene cancellato: i dati dell'owner (anche bonificati) non restano sul cloud.

## 7. Sul PC, dopo

1. Mettere `rt_it48k_ft1` accanto a `rt_it48k`; la config del Daily punta `--mtp` al nuovo pacco (prima un B-A-B col
   banco forzato a 131k del lab, OktoCGControl spento, come negli handoff).  Questa è una release: la fa l'owner.
2. Riportare i numeri in `HANDOFF_STRATA_UPSYNC_2026-10-11.md` (o il successivo) e nella memoria.

## 8. Tempi e rischi

| Fase | Tempo |
|---|---|
| boot, apt, clone, build sm_90 | 25–35 min |
| download GGUF 76 GB + pack | 10–30 min (in parallelo alla build) |
| trasferimenti dal PC (≈ 1 GB) | 2–10 min |
| cattura 3,5M token | 2–3,5 h |
| training 2 epoche | 40–90 min |
| export, bench, copia a casa | 20–30 min |
| **totale** | **5–7 h** |

Rischi: (1) la build su sm_90 non è mai stata fatta (il Dockerfile compila 75;80;86;89;120; CMake accetta 90) — se
nvcc si lamenta di `cluster`/PDL, aggiungere `-DCMAKE_CUDA_ARCHITECTURES=90`; (2) la velocità del percorso a finestre
sul H100 è una stima — misurarla con `--count 30` prima di lanciare tutto; (3) `setup.sh` potrebbe voler un passo
interattivo: `--yes` prende i default; (4) la cattura non è stata provata sulla GPU locale (bench.lock e VRAM occupata):
il primo `--count 30` sul pod è anche la sua prima prova vera; se `seq_0.json` manca, guardare
`capture/run_*.engine.log` ("strata mtp capture: on" deve esserci).
