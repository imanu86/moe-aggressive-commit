# Banco follow-up × profondità (21 settembre 2026)

**Domanda.** Il test 6×20k di Codex misurava solo blocchi da 20k, che nessuno manda davvero.
Quanto costa il prefill di un follow-up realistico (256-8192 token) man mano che la conversazione
si allunga, dato che a contesto vuoto si parte oltre i 400 t/s?

**Metodo.** Una sola conversazione in chat (`/v1/chat/completions`, come i client veri) che cresce
fino a ~133k token. Ogni passo aggiunge un messaggio utente di N token (testo ricavato dal fixture a
id con `/detokenize`), genera 8 token e rimette la risposta nella cronologia: la cache del prompt
copre tutto il contesto precedente. Il tempo di prefill è `timings.prompt_ms` del server.

- Livelli di profondità: 0, 33k, 66k, 99k, 116k (ognuno parte ~512 token dopo un confine di secchio
  KV da 16384, così la ri-riserva dell'area di lavoro non cade nelle celle piccole).
- Celle per livello, in quest'ordine: 256, 1024, 2048, 4096, 256\*, 1024\*, 8192
  (\* = ripetute, per il rumore; la 8192 è l'unica che attraversa un confine di secchio).
- Fra i livelli un riempimento da ~16k, che vale come punto «blocco grosso» e assorbe la deriva
  dovuta al template e alle risposte.
- Il runner aborta alla prima richiesta in cui la cache non copre il contesto precedente.

**Bracci** (`--braccio`):

| braccio | binari | slot | note |
|---|---|---|---|
| `x4` | `D:\ds4_work\p11_work\build\bin` (produzione) | 40 fissi | come «Qwen - CGControl - senza MTP - 40 slot.bat» |
| `m1` | `runtime-m1` del laboratorio di Codex | 70, elastici | cache esperti elastica + 8 strati in RAM sfrattabili, MTP spento |

Entrambi usano il modello GSQ-RCO IQ3_XXS e `reference_gsq_64.json` (stessi argomenti e stesse env
del lanciatore quotidiano). Il fixture è `ctx131k.ids.bin.gz` del laboratorio X4 di Codex. Tutto ciò
che sta nel laboratorio di Codex è usato in sola lettura. Le corse finiscono in
`D:\ds4_work\banco_followup_run\<data_ora>_<braccio>\`.

**Come si lancia** (staccato dalla shell di Claude, regola del 12/8):

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine='"C:\Users\imanu\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\imanu\source\repos\moe-aggressive-commit\docs\porto\banco_followup\banco_followup.py" --run --braccio x4'
  CurrentDirectory='D:\ds4_work\banco_followup_run' }
```

Il segnale di fine è la riga `FINE ok` / `FINE errore: …` in `STATO.txt`. Poi:

```powershell
python docs\porto\banco_followup\analizza_followup.py D:\ds4_work\banco_followup_run\<corsa>
```

Senza `--run` il runner stampa solo il piano delle 38 richieste.

**Difetto trovato per strada.** Una richiesta `/completion` grezza (prompt a vettore di token, 512 o
4608 token) come prima richiesta fa cadere il server con `CUDA error: an illegal memory access`
subito dopo `demand workspace tokens=508 kv=16384`: tre corse su tre, su entrambi i binari
(`20260921_064357`, `_064832`, `_065231_x4`). In chat non succede: il primo blocco è sempre il
preambolo del template (42-89 token a kv=256). I client di produzione passano tutti dalla chat.

I risultati stanno in `RISULTATI_21_SETTEMBRE.md`. `genera_bat_elastico.py` genera sul Desktop il
lanciatore della modalità adattiva.
