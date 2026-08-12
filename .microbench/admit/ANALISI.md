# Politica di ammissione per confine

## Diagnosi sul file corrente

Gli stati sono definiti in `ds4-p4a/ds4_cuda.cu:27959`: SSD cold,
RAM probation, RAM warm e VRAM protected. La metadata per coppia
`(layer, expert)` e la massa/frequenza lifetime sono in
`ds4-p4a/ds4_cuda.cu:28070`.

La mappa dei confini nel percorso enforce corrente e':

| Confine | Punto di decisione corrente | Comportamento corrente |
|---|---|---|
| SSD -> RAM probation | `cuda_moe_tiering_load_to_ram`, `ds4-p4a/ds4_cuda.cu:35245`, chiamata dal miss worker a `ds4-p4a/ds4_cuda.cu:39303` | `cuda_moe_tiering_pick_ram_slot` (`ds4-p4a/ds4_cuda.cu:33122`) cerca prima uno slot libero e poi un victim reclamabile. Senza G133 non confronta il punteggio del candidato col victim: se riesce ad acquisire il writer sostituisce comunque; se non trova un victim acquisibile rifiuta. Non consulta `policy_min_frequency`. |
| probation -> warm | osservazione a `ds4-p4a/ds4_cuda.cu:35507` | Non esiste un gate mass-LFRU distinto. Il solo passaggio probation -> warm durante l'osservazione e' quello G133 a `ds4-p4a/ds4_cuda.cu:35524`. Senza G133, `RAM_WARM` nasce soprattutto dalla demozione VRAM -> RAM (`ds4-p4a/ds4_cuda.cu:35955`); il commit VRAM contabilizza `ram_to_warm` ma porta il candidato direttamente in VRAM. |
| RAM -> VRAM | `cuda_moe_tiering_pick_vram_slot`, `ds4-p4a/ds4_cuda.cu:38409`, chiamata a `ds4-p4a/ds4_cuda.cu:39675` | Il gate di frequenza e' a `ds4-p4a/ds4_cuda.cu:38423`; poi vengono applicati slot libero, budget per finestra e confronto mass-LFRU col victim. |
| adattamento | blocco epoch in `cuda_moe_tiering_pick_vram_slot`, `ds4-p4a/ds4_cuda.cu:38471` | Regola solo il replacement budget VRAM. L'epoch viene aggiornato pigramente quando si entra nel selettore VRAM pieno. |

### Dove agisce `ram_admit_skips`

Tutti gli incrementi correnti sono dentro `cuda_moe_tiering_load_to_ram`:

- `ds4-p4a/ds4_cuda.cu:35260`: `pick_ram_slot` restituisce `-1`;
- `ds4-p4a/ds4_cuda.cu:35270`: lo slot non conserva il writer claim atteso;
- `ds4-p4a/ds4_cuda.cu:35281`: fallisce il resize dello scratch gia'
  esistente usato per una sostituzione (il contatore e' incrementato a
  `ds4-p4a/ds4_cuda.cu:35286`).

Il primo caso domina quando l'arena non ha slot liberi e nessun residente e'
reclamabile in quel momento. Il selettore esclude, fra gli altri, slot con
reference attive, slot riservati al wrap, residenti toccati nella call corrente
e backing VRAM non reclamabile (`ds4-p4a/ds4_cuda.cu:33171`). Quindi
`ram_admit_skips` non distingue "arena piena", "victim occupato" e
"writer perso": e' un contatore aggregato di mancata ammissione RAM.

### Perche' `policy_min_frequency_skips` resta a zero

`policy_min_frequency` non e' installato sul confine SSD -> RAM. Viene letto
solo nel selettore RAM -> VRAM (`ds4-p4a/ds4_cuda.cu:38423`), dopo che
`cuda_moe_tiering_observe_route` ha gia' incrementato la frequenza lifetime
del candidato (`ds4-p4a/ds4_cuda.cu:35521`). La frequenza non decade alla fine
di `CLOCK_CALLS`. Con soglia 3, i candidati che arrivano al selettore VRAM
hanno quindi normalmente gia' almeno tre osservazioni; gli esperti respinti
prima al confine SSD -> RAM non raggiungono mai quel gate. Questo spiega
insieme `policy_min_frequency_skips=0` e l'elevato `ram_admit_skips`.

## Disegno della patch

La patch e' opt-in per confine. I nomi effettivi sono:

- `DS4_EXPERT_TIER_ADMIT_KNOCKS_SSD`, default `0`;
- `DS4_EXPERT_TIER_ADMIT_KNOCKS_WARM`, default `0`, cioe' nessun gate
  probation -> warm separato come oggi;
- `DS4_EXPERT_TIER_ADMIT_KNOCKS_VRAM`: se non impostato eredita
  `DS4_EXPERT_TIER_MIN_FREQUENCY` (default `3`), ma il nuovo ramo windowed
  viene attivato solo quando la nuova variabile e' impostata esplicitamente;
- `DS4_EXPERT_TIER_ADMIT_MASS_BYPASS_SSD`, default `0` (disabilitato);
- `DS4_EXPERT_TIER_ADMIT_MASS_BYPASS_WARM`, default `0`;
- `DS4_EXPERT_TIER_ADMIT_MASS_BYPASS_VRAM`, default `0`;
- `DS4_EXPERT_TIER_ADMIT_ADAPTIVE`, default `0`.

Le due bypass warm/VRAM completano la telemetria richiesta per tutti i
confini. Una bypass SSD/warm positiva richiede anche knocks positivi, salvo
modalita' adaptive; una bypass con gate zero non avrebbe alcun effetto.
Le nuove manopole richiedono la policy `mass-lfru`.

La sola struttura nuova e'
`uint16_t admit_knocks[CUDA_MOE_LAYER_COUNT * 256]` in
`ds4-p4a/ds4_cuda.cu:28177` dopo applicazione: 11.008 contatori, 22.016 byte,
allocati staticamente dentro lo stato tiering. Nessuna allocazione e' stata
aggiunta nel percorso caldo. Il percorso di sostituzione continua a usare lo
scratch thread-local preesistente in `cuda_moe_tiering_load_to_ram`.

La tabella e' aggiornata una volta per coppia selezionata. Alla fine di ogni
finestra `DS4_EXPERT_TIER_CLOCK_CALLS`, tutti i contatori vengono dimezzati;
se sono saltate piu' finestre, lo shift riflette il numero di finestre fino a
un massimo di 16. Il codice e' in `ds4-p4a/ds4_cuda.cu:31918` dopo
applicazione.

### A) SSD -> RAM

Il gate e il ramo legacy separato sono in
`ds4-p4a/ds4_cuda.cu:35625` dopo applicazione. Se il confine SSD non e'
abilitato viene chiamato il selettore originale senza modificarne il blocco.

Con il confine attivo, knocks o mass bypass sono valutati prima di leggere
SSD. Il selettore opt-in duplicato e' in
`ds4-p4a/ds4_cuda.cu:33483`: cerca gli slot liberi come il selettore corrente;
se l'arena e' piena calcola il medesimo LFRU RAM per candidato e residenti,
sceglie il residente reclamabile col punteggio minimo e lo acquisisce solo se
`candidate_score > victim_score`. Il commit incrementa
`admit_replaced_worse_ssd` soltanto dopo che lettura e sostituzione sono
riuscite (`ds4-p4a/ds4_cuda.cu:35872`).

### B) probation -> warm

Il gate e' in `cuda_moe_tiering_observe_route`,
`ds4-p4a/ds4_cuda.cu:35922` dopo applicazione. E' attivo solo per il confine
warm. Al superamento di knocks o bypass cambia lo stato in `RAM_WARM` e
incrementa `ram_to_warm`.

Se questo gate e' attivo, il selettore VRAM non lascia saltare direttamente
un candidato ancora probation (`ds4-p4a/ds4_cuda.cu:38848`). Con gate warm
disabilitato rimane possibile il comportamento corrente probation -> VRAM.

### C) RAM -> VRAM

Il ramo e' in `cuda_moe_tiering_pick_vram_slot`,
`ds4-p4a/ds4_cuda.cu:38838` dopo applicazione. Se la nuova variabile VRAM non
e' stata impostata, viene eseguito il blocco originale basato su
`policy_min_frequency`; se e' impostata, usa i knocks decaduti nella finestra
e l'eventuale mass bypass. Budget, selezione victim, hysteresis, reservation,
copy e commit restano successivi e invariati.

### D) soglia adattiva

`DS4_EXPERT_TIER_ADMIT_ADAPTIVE=1` abilita tutti e tre i confini. La pressione
di ogni confine e' calcolata a fine `CLOCK_CALLS` come

`replacements / (free_promotions + replacements)`.

Con pressione almeno `0,5` la soglia sale di un knock; con pressione al
massimo `0,25` scende di uno fino alla soglia base (per una base zero,
l'adaptive usa un minimo operativo di 1). Il massimo e' 65.535.

SSD usa ammissioni in slot libero contro sostituzioni RAM; VRAM usa gli stessi
eventi che alimentano `policy_free_promotions` e `policy_replacements`. Warm
non ha nel codice corrente una capacita' o un victim: le sue transizioni sono
quindi free promotions e la sua pressione resta zero. Non e' stata inventata
una cap warm che cambierebbe la semantica del tier.

L'adattamento si aggancia alla stessa finestra
`policy_clock_calls/DS4_EXPERT_TIER_CLOCK_CALLS` e allo stesso modello
free-vs-replacement del budget adattivo esistente. Non condivide
`policy_epoch`: quell'epoch viene avanzato soltanto dal selettore VRAM pieno,
troppo tardi per i gate SSD e warm, e condividerlo anticiperebbe il reset del
budget esistente. Il cursore admission separato evita quella modifica del
percorso comune.

## Compatibilita' OFF-default

Con tutte le nuove variabili assenti:

- `policy_admit_ssd_enabled`, `policy_admit_warm_enabled` e
  `policy_admit_vram_enabled` sono falsi;
- SSD -> RAM chiama il blocco/selettore originale;
- probation -> warm non esegue il nuovo gate;
- RAM -> VRAM esegue il blocco originale `policy_min_frequency`;
- la tabella knocks non viene aggiornata e l'adaptive non gira.

La riga finale aggiunge comunque la telemetria richiesta; le nuove soglie
correnti riportano `0/0/3` e i nuovi contatori restano zero. Questa e' l'unica
differenza osservabile prevista nel run di controllo oltre alla presenza
della metadata statica.

I campi aggiunti a entrambe le varianti della riga `[expert-tiering] final`
sono in `ds4-p4a/ds4_cuda.cu:32027` e `ds4-p4a/ds4_cuda.cu:32095` dopo
applicazione:

- `admit_knocks_skips_ssd`, `_warm`, `_vram`;
- `admit_mass_bypass_ssd`, `_warm`, `_vram`;
- `admit_replaced_worse_ssd`;
- `admit_current_knocks_ssd`, `_warm`, `_vram`.

## Verifica effettuata

Non e' stato compilato ne' eseguito alcun server. Il sorgente corrente non e'
stato modificato. Sono stati eseguiti soltanto controlli statici sul diff:
assenza di whitespace error, corrispondenza fra specificatori e argomenti dei
due `fprintf` finali, assenza di primitive di allocazione nelle righe aggiunte
e applicabilita' del diff al file corrente.
