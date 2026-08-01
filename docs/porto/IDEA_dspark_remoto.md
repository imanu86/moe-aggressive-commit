# IDEA DA RIPRENDERE — DSpark su un'altra macchina, via LAN

**Dell'utente, 1/8 sera.** *"Potremmo usare DSpark su Mac e delegare quella fetta di lavoro,
leggendo solo pochi KB via LAN?"* — poi: *"con pipeline parallelism?"*

Messa da parte per non deragliare dalla baseline, ma **non e' una fantasia**: ha una parte
solida, un ostacolo preciso, e un motivo per cui e' particolarmente adatta a NOI.

## Perche' regge: l'interfaccia e' davvero minuscola

La speculazione ha una struttura che separa bene:

```
abbozzatore -> bersaglio   k token proposti          pochi byte
bersaglio   -> abbozzatore stato nascosto ai layer   4096 x 3 layer
                           bersaglio [40,41,42]      ~24 KB a f16, ~48 a f32
```

A 5 t/s sono ~250 KB/s. **Su una LAN gigabit e' niente**, e il tempo di andata e ritorno
(0,2-1 ms) e' trascurabile contro i ~200 ms del nostro token. La banda non e' il problema.

## Perche' per NOI vale piu' che per altri

Non e' che il calcolo del drafter ci pesi in astratto: e' che **su questa macchina il drafter
paga tre volte**.

```
4,5 GiB   la riserva VRAM che DSpark chiede (DS4_DSPARK_CACHE_RESERVE_GB, default 4+0,5)
          su 12 GB dove ne abbiamo gia' solo 1,02 liberi al dimensionamento della cache
+48%      il tempo che il drafter CPU spende FUORI dal grafo, misurato il 31/7
135 slot  la cache esperti che otteniamo invece di 253: liberare VRAM la sposta direttamente
```

**Spostare l'abbozzatore altrove libera VRAM che qui vale piu' che altrove.** E' l'unica delle
nostre leve che compra spazio invece di consumarlo.

## L'ostacolo, ed e' di ingegneria non di fisica

**ds4 non ha un protocollo di drafter distribuito.** L'integrazione DSpark e' in-processo:
`ds4_gpu_register_support_map(map, size, bias)` mappa il sidecar nello spazio del processo, con
`bias` oltre la fine del modello (`ds4.c:55524`). Non esiste un'interfaccia di rete fra
abbozzatore e verificatore: andrebbe costruita.

E c'e' un guardiano che oggi blocca comunque la combinazione:
`ds4.c:56365` rifiuta `--ssd-streaming` insieme a `--mtp`, e il sidecar DSpark si carica
proprio con `--mtp`. Lo streaming non possiamo spegnerlo.

## Sul pipeline parallelism: NON e' la stessa cosa, e non serve qui

Upstream ha `ds4_distributed.*` (PP per strati, N worker) e `ds4_tp.*` (TP a 2 ranghi), ma solo
in `ds4-upstream-cuda-measure/`. **Sono un'altra cosa.**

> Il PP spezza **il modello** fra macchine: ogni token attraversa tutti gli stadi in sequenza,
> quindi la latenza per token **peggiora** e si guadagna solo throughput aggregato su richieste
> concorrenti. Noi siamo **un utente solo** e ci interessa la latenza.

La delega dell'abbozzatore e' invece **funzionale**, non per strati: due modelli diversi, due
macchine, e la comunicazione avviene una volta per blocco di bozza invece che una volta per
strato. **E' la topologia giusta per un utente singolo**, il PP no.

## Cosa verificare quando la si riprende

1. **Cosa consuma davvero DSpark dal bersaglio.** Ho visto `target_layer_count` e
   `target_layers[]` (`ds4.c:2559-2560`), ma **non ho verificato la forma esatta** dello stato
   passato agli stadi. Se servisse piu' dello stato nascosto ai tre layer, il conto della banda
   cambia.
2. **Se c'e' una macchina.** L'idea nasce con "su Mac": va confermato quale hardware c'e'
   davvero in rete e se regge un modello da ~20 miliardi di parametri.
3. **Il guardiano `--mtp` + `--ssd-streaming`**, che va tolto comunque (vedi
   `resume-20260801-porto-completo`): la sua premessa e' la issue upstream #639, cioe' che lo
   streaming non abbia residenza persistente. Quella residenza l'abbiamo scritta noi.

## Perche' NON adesso

Manca ancora la baseline: cinque run e nessun numero confrontabile col riferimento di 4,42 t/s.
**Aggiungere una macchina e un protocollo di rete a un sistema che non sappiamo ancora
misurare** e' il modo piu' rapido per non capire piu' niente. Prima il numero, poi questa.
