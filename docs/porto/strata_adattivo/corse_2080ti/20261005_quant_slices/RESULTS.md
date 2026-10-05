# Fette di esperti IQ3_S (ISTA-DASLab) e UD-IQ4_XS (unsloth) — 2026-10-05

Domanda: una quantizzazione diversa degli esperti (piu' alta o piu' "facile" da decodificare) rende piu'
veloce il percorso CPU o GPU? I pesi di altri file si possono mescolare con i nostri?

## Download parziale

`hf_slice.py`: richieste HTTP a intervalli, solo intestazioni + primi 48 esperti degli strati 0/1/35.
Esito: due GGUF "fetta" con gli stessi nomi, tipi e righe dei file d'origine (non versionati, in
`C:\Users\imanu\Downloads\strata_slices\`), manifest con sha256 e tipi di tutti gli strati
(`*.gguf.json`), allocazione RCO dell'IQ3_S (`iq3s.rco-allocation.txt`).

| Sorgente | Revisione | Scaricato |
|---|---|---:|
| ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF, `IQ3_S/` | ed59f920 | 275 MiB |
| unsloth/Qwen3.8-Flash-Next-GGUF, `UD-IQ4_XS/` | 38bb39ee | 320 MiB |

Tipi degli esperti (gate/up + down) sui 48 strati:

| Modello | Composizione |
|---|---|
| nostro GSQ-RCO IQ3_XXS (70,6 GiB) | IQ3_S 13, IQ2_XS 10, IQ2_S 10, IQ2_XXS 9, IQ3_XXS 6; down Q2_0 in 30, IQ4_NL in 18 |
| ISTA GSQ-RCO IQ3_S (77,9 GiB) | IQ3_XXS 17, IQ2_S 20, IQ3_S 10, IQ4_XS 1; down Q2_0 in 9, IQ4_NL in 39 |
| unsloth UD-IQ4_XS | IQ3_S 47, IQ4_XS 1; down IQ4_NL 43, Q8_0 5 |

L'"UD-IQ4_XS" di unsloth negli esperti e' IQ3_S, non IQ4_XS. ISTA-DASLab pubblica per questo modello solo
IQ2_XS, Q2_0, IQ3_XXS e IQ3_S, piu' una variante Coder IQ1_M con meta' degli esperti potati (non mescolabile).

## Stessi pesi? (`cmp_slices.py`, `cmp_slices.txt`)

Coseno mediano riga per riga dei pesi dequantizzati, primi 8 esperti, contro il nostro IQ3_XXS:

| Tensore | nostro | ISTA IQ3_S | coseno | unsloth | coseno |
|---|---|---|---:|---|---:|
| L0 gate/up | IQ2_XS | IQ3_XXS | 0,939–0,940 | IQ3_S | 0,937–0,938 |
| L0 down | IQ4_NL | IQ4_NL | 0,991 | IQ4_NL | 0,991 |
| L1 gate/up | IQ2_XXS | IQ2_S | 0,911–0,912 | IQ3_S | 0,925–0,926 |
| L1 down | Q2_0 | Q2_0 | 0,934 | IQ4_NL | 0,911 |
| L35 gate/up | IQ3_XXS | IQ3_S | 0,969–0,970 | IQ3_S | 0,971 |
| L35 down | IQ4_NL | IQ4_NL | 0,994 | IQ4_NL | 0,995 |

ISTA IQ3_S contro unsloth IQ3_S sullo strato 35: 0,994 (gate/up) e 0,996 (down).

Nessuna rotazione o permutazione: tutti e tre i file contengono gli stessi pesi base. Le differenze
seguono i bit del formato; l'imatrix diversa (ISTA contro unsloth, stesso formato) pesa molto meno
(0,994). Mescolare a granularita' di esperto e' quindi tecnicamente possibile; la prova decisiva resta
la KL in teacher forcing sul modello intero.

## Velocita' CPU (cpu_format_bench, 8 thread, 1 token, us per esperto gate+up)

| Formato | nostro | ISTA | unsloth |
|---|---:|---:|---:|
| IQ2_XXS / IQ2_S (L1) | 51–54 | 51 (IQ2_S) | — |
| IQ3_XXS | 56–58 | 53 (L0) | — |
| IQ3_S | 83 (riquantizzato) | 66 (L35) | 82–85 |

Down IQ4_NL 27–31 us, Q2_0 20 us, come nel nostro modello.

## Velocita' GPU (native_expert_bench, 10 esperti, decode once)

| Formato | 1 token us | 4 token us |
|---|---:|---:|
| IQ2_XXS + Q2_0 (nostro L1) | 81–85 | 151 |
| IQ2_S + Q2_0 (ISTA L1) | 89–91 | 164 |
| IQ3_XXS + IQ4_NL (nostro L35, ISTA L0) | 93–105 | 156–166 |
| IQ3_S + IQ4_NL (ISTA L35, unsloth) | 102–116 | 169–182 |

La GPU era condivisa con altri programmi (circa 29% di utilizzo): rumore del 5–10%.

## Conclusioni

- IQ3_S non e' piu' veloce ne' su CPU (+15–50%) ne' su GPU (+7–15%), e pesa il 7% in piu' per esperto:
  in VRAM ne entrerebbero meno. Come leva di velocita' e' esclusa.
- IQ2_S costa su GPU l'8–10% piu' di IQ2_XXS.
- Come leva di qualita': l'IQ3_S di ISTA e' lo stesso laboratorio e lo stesso procedimento (77,9 contro
  70,6 GiB), ma non e' uniformemente "un gradino sopra": i bit in piu' vanno soprattutto al down (IQ4_NL in
  39 strati contro 18) e ad altri tensori; sul gate/up la miscela e' diversa (IQ3_S in 10 strati contro 13
  del nostro, IQ2_S in 20 contro 10). Sugli strati 0/1/35 scaricati il gate/up e' piu' alto del nostro.
  Cambia l'output, quindi solo opzione da provare sul campo.
