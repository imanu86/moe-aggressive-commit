# Decode: adattivo M2 contro 40 slot fissi (21 settembre 2026, pomeriggio)

Banco `banco_decode.py`: stesso documento troncato a ~1k, ~50k e ~100k token, 512 token generati, greedy,
senza MTP, una corsa per braccio, una dopo l'altra nelle stesse condizioni di macchina (desktop con ~2,1 GB di
VRAM occupati). Corse: `D:\ds4_work\qwen_gateway_run\20260921_14*_decode_produzione` (M2, server di
produzione avviato dal nuovo bat, cache elastica a 69-72 slot) e `…_decode_x4` (binari p11, 40 slot fissi).

| contesto | M2 adattivo: decode | 40 slot: decode | scarto | M2: prefill | 40 slot: prefill |
|---|---|---|---|---|---|
| ~1k (prima richiesta, a freddo) | 13,5 t/s | 14,8 t/s | −9% | 185 t/s | 218 t/s |
| ~50k | 17,1 t/s | 19,2 t/s | −11% | 367 t/s | 385 t/s |
| ~100k | 18,3 t/s | 19,8 t/s | −7% | 281 t/s | 293 t/s |

**L'adattivo M2 non è migliorativo in velocità: è il 7-11% più lento in decode e il 4-5% nel prefill.** Il suo
valore è la tenuta sotto pressione di VRAM e di RAM, non i t/s. Cause plausibili, non separate: gli 8 strati
di esperti nel deposito RAM sfrattabile, la cache ricostruita da 30 slot dopo ogni prefill, il costo della
politica. Più slot non pagano dentro 512 token generati a cache fredda.

## Da dove vengono i «25-27 t/s»

Dai log storici del server di produzione (generazioni da almeno 100 token):

| lanciatore | data | generazioni | mediana | min-max |
|---|---|---|---|---|
| p11, 40 slot, senza MTP (uso vero con DSH, prompt medi 90k) | 19/9 | 193 | 19,4 t/s | 17,4-22,3 |
| p11, 40 slot, senza MTP (prompt medi 74k) | 20/9 | 95 | 22,7 t/s | 17,7-24,1 |
| p11, 70 slot, senza MTP (una prova breve) | 18/9 | 1 | 23,6 t/s | — |
| p11, 70 slot, MTP1 | 18/9 | 9 | 18,4 t/s | 3,4-21,3 |

I 25-27 t/s dei registri sono misure di banco a contesto corto (27,25 t/s «decode lossless» con MTP a 32k,
24,6 senza MTP). Nell'uso vero a 75-100k di contesto il server a 40 slot ha sempre fatto 19-23 t/s: i 19-20
di oggi sono in linea, non un peggioramento.

## Cosa resta da misurare

- p11 a 64-70 slot FISSI con lo stesso banco: dice se, con la VRAM che il desktop lascia libera oggi, più slot
  pagano a 50-100k (la curva del 13/9 dava +11% fra 32 e 64 slot, ma a contesto corto);
- MTP1 sopra la configurazione vincente (Codex: +9% in decode sull'elastico, pagato nel prefill profondo);
- il decode a regime su generazioni lunghe (2-4k token), dove la cache esperti ha il tempo di scaldarsi.
