# POD PLAYBOOK — come si fanno i test su RunPod (track paralleli)

> Regole vincolanti per OGNI test su pod dei track REAP/DSpark. Budget autorizzato dall'utente:
> **$1-2 TOTALI per track.** Balance account ~$23: controllalo prima e dopo, riporta la spesa.

## 1. Scelta GPU (economia)
- **RTX 3090 24GB community** (~$0.22-0.46/h) = la scelta giusta: è **sm_86 come il 3060** della
  workstation → stessi flag di build, binari confrontabili. Codex ci ha già validato i patch.
- NIENTE H100/H200/B200: non servono per questi test e bruciano il budget in un'ora.
- Container disk: **130GB** se scarichi il modello 2-bit (86.7GB); **30GB** se ti basta sorgente+MTP.
- `volumeInGb: 0` (il network volume scrive a 1MB/s — lezione appresa; usa il disco container).

## 2. Deploy / terminate (API GraphQL)
- Key API: `C:\Users\imanu\Desktop\Runapod.txt` sulla workstation. **MAI stamparla in chat/log/commit.**
- Endpoint `https://api.runpod.io/graphql`, header `Authorization: Bearer <key>` **+ `User-Agent`
  da browser** (senza → 403 Cloudflare).
- Immagine benedetta: `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` (nvcc 12.8 incluso), ports `22/tcp`.
- Mutation `podFindAndDeployOnDemand`; poi query pod per ip/porta ssh (usa l'**ssh TCP diretto ip:porta**,
  non il proxy hostname: più stabile).
- **A FINE TEST: `podTerminate` SUBITO + verifica `myself { pods }` vuoto.** Un pod idle dimenticato
  mangia il budget di tutti. Mai lasciarlo acceso >15 min senza un job attivo.

## 3. Setup sul pod (ds4)
```bash
git clone https://github.com/antirez/ds4 && cd ds4 && git checkout 80ebbc3   # PIN, stessa base nostra
# patch nostri: scp dalla workstation (repo/patches/ds4/*.patch) → git apply nell'ordine 0001..000N
make cuda CUDA_ARCH=sm_86
# modello (repo HF pubblico antirez/deepseek-v4-gguf, DC-network ~10-20 min per 86.7GB):
# 2-bit: DeepSeek-V4-Flash-IQ2XXS-*imatrix.gguf ; MTP: DeepSeek-V4-Flash-MTP-*.gguf (3.8GB)
```
- ⚠️ **quirk ssh-proxy RunPod:** nohup/setsid/tmux MUOIONO alla chiusura ssh. Job >5 min → lancialo
  dentro un **ssh long-lived** tenuto aperto dalla workstation (`ssh -o ServerAliveInterval=20 ip -p porta "bash job.sh"`,
  in background locale), NON con nohup sul pod.
- ⚠️ **mai bulk-download dal pod via ssh-proxy** (throttle ~11MB/s). I tuoi artefatti (log/CSV/mask)
  sono piccoli → scp diretto ok. Non scaricare mai il modello verso casa.

## 4. METODO DI MISURA (vincolante — pena: risultato non valido)
1. **Prompt fisso** scritto in `meta.json`, greedy/temp 0, `--nothink`, `-n` fisso, `DS4_SPEX_STATS=1`.
2. **1 run di warm-up SCARTATA** + **≥2 run misurate** → riporta la mediana. Etichetta SEMPRE
   cold/warm (stato page-cache).
3. **Transferibilità — dichiarala:** i pod 3090 hanno spesso 64-128GB RAM → il modello sta in RAM =
   regime DIVERSO dal 3060 (28GB). **Routing trace, saliency, acceptance-rate MTP = proprietà del
   MODELLO → trasferiscono. I t/s wall-clock NON trasferiscono** → mai presentarli come "velocità sul 3060".
4. **Ogni numero deve avere il file:** log/CSV via scp → `runs/<track>/<data>_<test>/` nel repo +
   `meta.json` (GPU, config, cmdline, costo pod) → commit+push sul TUO branch. Un numero senza file
   su disco = non esiste (regola anti-confabulazione, vale anche per te).
5. Controlli: dove misuri un metodo, misura anche il **controllo** (random / baseline reattivo) a pari
   budget — rigore da paper.

## 5. Sicurezza
- MAI stampare/committare: RunPod key, token HF, chiavi ssh. Se un tool li logga, redigi prima del commit.
- Ricorda: la key RunPod è segnata "da ruotare" — usala ma non peggiorare l'esposizione.

## 6. Lezioni operative (dai pod già fatti — track REAP 2026-07-05)
- **Gate-check CUDA APPENA dentro, PRIMA di scaricare il modello**: `nvidia-smi && nvcc --version` +
  un micro-kernel di prova. Una macchina con CUDA rotto a livello container esiste e RunPod te la
  RIASSEGNA a ogni deploy con gli stessi filtri → per uscirne, cambia i filtri (es. alza `minVcpuCount`).
- **Determinismo: greedy temp-0 su ds4-CUDA NON è bit-riproducibile** (repeat dello stesso prompt:
  1933/2720 righe di routing diverse). Le trace sono CAMPIONI della distribuzione di decode: robustezza
  via split-half/statistica, MAI via diff bit-exact. Vale anche per i test di correttezza ON/OFF.
- **Profiler upstream (`--expert-profile`/`DS4_EXPERT_HOTLIST`) è Metal-only**: su CUDA non si attiva.
  Non contarci per cross-check.
- Invariante sanity per trace con pesi: somma dei 6 gate-weights per riga ≈ 1.5 (`expert_weights_scale` Flash).

## 7. Run notturni LOCALI (lezione 2026-07-06)
- **tmux/setsid dentro WSL NON sopravvive a sleep/spegnimento della macchina Windows** (WSL muore
  con l'host → muore tutto). "Puoi spegnere tranquillo" con un run locale in corso = run morto.
- Regola: run notturno locale ⇒ sospensione Windows DISATTIVATA (powercfg) e coperchio/alimentazione
  gestiti; altrimenti il run notturno si fa su POD (che vive di suo). Il watcher che deve raccogliere
  il risultato muore anche lui col PC: prevedere raccolta a freddo al mattino (log su disco).
