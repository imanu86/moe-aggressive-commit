# MANDATO PRONTO — blocco 7, tiering e promozione

**Da lanciare quando il blocco 6 atterra**, sullo **stesso worktree e stesso ramo**
(`ds4-port-blk6`, `port/blk6-vramcache`): 6, 7 e 8 condividono la transazione e non possono
stare su rami diversi.

```powershell
Get-Content -Raw docs\porto\mandato_blk7_tiering.md | & codex exec `
  -C "C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port-blk6" -s workspace-write - `
  *> "blk7_tiering.log"
```

---

LAVORO DI IMPLEMENTAZIONE. Scrivi codice, nel worktree indicato e SOLO li'.

  IL TUO WORKTREE:  C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-port-blk6
                    branch port/blk6-vramcache. **Contiene gia' l'adattatore (blocco 3) e la
                    cache VRAM (blocco 6)**: leggi `PORT_BLOCK3_ADAPTER.md` e
                    `PORT_BLOCK6_VRAMCACHE.md` PRIMA di scrivere una riga.
  RIFERIMENTO:      C:\Users\imanu\source\repos\moe-aggressive-commit\ds4-p4a
                    il nostro fork, HEAD af84c42. **SOLO LETTURA.**

**TUTTO CIO' CHE SCRIVI DEVE STARE DENTRO LA TUA RADICE.** Sotto `workspace-write` il resto del
disco e' negato e te ne accorgeresti solo alla fine, a lavoro fatto.

OBIETTIVO: **tiering, admission, promozione e rollback** (blocco 7).

## LA REGOLA CHE GOVERNA TUTTO IL BLOCCO

Il nucleo 6-7-8 deve atterrare **spento** e accendersi in **un solo passo finale**.
`reservation`, `victim`, `publish` e `refund` o ci sono tutti e quattro, o non si attiva
niente. **Non aggiungere un flag che accende il tiering da solo**: sarebbe attivabile prima
che il route worker (blocco 8) esista, e la transazione resterebbe monca.

## L'INVENTARIO, gia' fatto — sono ~4.000 righe

In `ds4-p4a/ds4_cuda.cu`. Non ricostruirlo, verificalo:

```
33359-33388   mode/policy requested            default OFF
33390-33626   parser configurazione tier/G133  237 righe, solo validazione
33644-33922   helper epoch/heat/candidatura    279  g133_advisory_*, mark_promotion,
                                                    record_observation, decayed_heat
33924-33966   budget G133 reserve/refund        43  PARTE DELLA RESERVATION
33968-34058   LFRU e admission gate             91  score, soglie adattive
34060-34082   clear_owned_slots                 23  ownership RAM
34084-34291   report_and_reset                 208
34293-34306   request_boundary_reset            14
34308-34360   reserve_open_router_slots         53  DIFFERIBILE
34362-34892   tiering_prepare                  531  costruzione autorita' tier e RAM
34897-34951   snapshot_ram_ptrs / ram_ptrs      54
35448-35559   pick_ram_slot                    112  VICTIM RAM
35563-35679   pick_ram_slot_admit              117  victim con admission margin
37773-37837   admission_pread                   65  lettura SSD per ingresso RAM
37839-38125   load_to_ram                      287  caricamento e pubblicazione tier RAM
38151-38202   observe_route                     52  heat/frequency/mass PRIMA dell'enforce
38204-38232   tick/epoch di promozione          29
38354-38616   stage cold->2bit (+ IQ1)         262  DIFFERIBILE
38618-38620   demote_cache_entry                 3
41950-41959   mass_lfru_score                   10
41977-42198   pick_vram_slot                   222  CREA LA RESERVATION
42200-42264   commit_vram_reservations          65
42266-42295   refund_failed_promotions          30
42328-42350   firma/consumo failure scoped      23  evita una seconda invalidazione totale
42352-42444   scoped_invalidate                 93  rollback mirato DOPO prova di quiescenza
42555-42615   finish_vram_reservations          61  TERMINALE UNICO
43092-44296   enforce_request                 1205  orchestrazione di tutte le miss
```

## COSA NON PORTARE, ed e' la parte difficile

Le **1.205 righe** di `enforce_request` contengono i rami **G73, G132, demand pipeline, nested
residual e DOV**. **Non copiarle alla cieca.**

> Porta **il percorso specializzato standard con la transazione completa**, e lascia i rami
> sperimentali **spenti**.

Differibili anche: `reserve_open_router_slots`, `stage_observed_quant_cold_to_2bit_ram`,
`stage_iq1_cold_to_2bit_ram`.

**Se non riesci a separare un ramo sperimentale dal percorso standard, dillo** invece di
portarti dietro anche quello: e' un'informazione, non un fallimento.

## DUE FATTI MISURATI CHE CAMBIANO LE SCELTE

**(1) L'imbuto.** `DS4_CUDA_PREFILL_TIER_RESERVE_SLOTS` vale **128 su 4551 slot** di arena: il
96,2% delle promozioni viene respinto **per mancanza di posto, non per merito**. Se porti
l'admission gate senza portare anche il conto di quanti slot restano davvero disponibili, il
gate misura la cosa sbagliata.

**(2) La vittima.** Il backbone e' usato dal **99,84% dei token**. Una volta abbiamo scelto
*lui* come vittima al cambio di dominio: 141.000 sfratti contro 0, con una variabile sola.
**Il selettore non deve poter scegliere un tensore non-esperto.**

## VINCOLO DELL'UTENTE, non negoziabile

*I meccanismi di promozione e pruning che servono al modello standard devono restare
INVARIATI.* Quello che porti si affianca. Con la politica spenta, il decode deve comportarsi
**identico a upstream**.

## VINCOLI DI PROGETTO

- `ds4_gpu_tensor` resta `{ptr, bytes, owner, device_id}`. **Niente campi aggiunti.**
- **Nessuna seconda API pubblica.** Dietro `ds4_gpu_stream_expert_cache_*`, non accanto.
- **Solo single-GPU**: c'e' un guard che rifiuta `g_n_gpus != 1`.
- **Additivo**: upstream resta compilabile su Linux.

## VERIFICA

```
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" ^
  -S . -B build-blk7 -G Ninja -DCMAKE_MAKE_PROGRAM="C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe" ^
  -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_CUDA_COMPILER="C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" ^
  -DCMAKE_CUDA_ARCHITECTURES=86 && ^
"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe" --build build-blk7 --parallel 6
```

Senza `-DCMAKE_C_COMPILER=cl` espliciti CMake non trova il compilatore nemmeno sotto vcvars.

**Fixture**: la transazione. Riserva, fai fallire il caricamento a meta', e verifica che il
refund riporti budget e stato esattamente com'erano e che la vittima non resti sovrascritta a
meta'. **E' il caso che rompe tutto in silenzio se sbagliato.**

**Rapporto** in `PORT_BLOCK7_TIERING.md` **nella radice del tuo worktree**: cosa hai portato
con le righe, quali rami hai lasciato spenti e come, la forma esatta della transazione, e cosa
serve al blocco 8 per chiuderla. Committa sul tuo branch.

Rispondi in italiano, con righe esatte.
