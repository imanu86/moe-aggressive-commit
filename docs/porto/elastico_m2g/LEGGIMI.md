# M2g — M2 con il cancello RAM della crescita corretto (28 settembre 2026)

**Difetto di M2.** `llama_moe_ram_growth_gate` (`llama-moecache-policy.h` di O2) nega ogni crescita della cache
elastica sotto 2 GiB di RAM disponibile, e dopo il blocco finche' la RAM non resta 15 s sopra 2,5 GiB. Il deposito RAM
sfratta esperti per tenere la RAM proprio a 2 GiB: con altri programmi aperti la RAM si ferma li' e il cancello non si
riapre piu'. Il primo prefill rilascia tutta la cache (M2), e da li' la cache resta a 0 slot per tutta la sessione anche
con 7,4 GB di VRAM libera, pur con `pending_ram_bytes = 0` (la crescita non chiedeva RAM).

**Correzione (3 punti in `src/llama-moecache.cpp`, `m2g-cancello-ram.patch`).** Il cancello si applica solo quando la
crescita alloca RAM (trasporti RAM nuovi, `pending_ram_bytes > 0`); `pending_ram_bytes` e' ricalcolato anche nel resize
(il cambio d'area dopo il prefill cresce senza passare dal piano). Con RAM libera sopra 2,5 GiB M2g si comporta come M2.

**Build.** `build_m2g_overlay.py`: ricompila solo `llama-moecache.cpp` coi flag O2, ricollega `llama.dll` con
l'oggetto `llama-context.cpp` di M2; tutto il resto copiato da `runtime-m2` (= `bin_elastico_m2`, verificato con SHA).
Runtime in `D:\ds4_work\elastico_m2g\runtime-m2g`, `llama.dll` 338f1dcb. La produzione non e' toccata.

## Misura (stessi prompt, stessa configurazione del bat con `-c 139264`, altri programmi aperti)

| | M2 (produzione) | M2g |
|---|---:|---:|
| VRAM altri programmi al lancio | 4.557 MiB | 4.681 MiB |
| slot della cache durante il decode | 0 | 42-55 |
| `growth_blocked_ram` | 555 | 0 |
| L01@32k prefill freddo / decode | 365 / 7,25 t/s | 406 / 18,80 t/s |
| L02@32k decode | 7,15 t/s | 18,86 t/s |
| L01@131k prefill / decode | 229 / 7,01 t/s | 274 / 16,43 t/s |
| L02@131k decode | 6,98 t/s | 16,99 t/s |
| **decode aggregato** | **7,09 t/s** | **17,71 t/s (x2,5)** |

M2g non rende il daily piu' veloce del daily a RAM libera (21/9, 100k, col deposito: 19,7-19,9 t/s): gli toglie il
crollo sotto pressione di RAM, candidato per gli 11 t/s dell'uso reale. Resta il difetto noto di M2: ogni resize svuota
tutta la cache, e M2g ne fa ~15 per sessione fra 42 e 55 slot (la banda morta di M3 li toglierebbe).
Corse: `../strata_prova/corse/20260928_185726_daily_m2_c139k_vram4557_tutto` e `.../20260928_200715_m2g_c139k_vram4681_tutto`.
