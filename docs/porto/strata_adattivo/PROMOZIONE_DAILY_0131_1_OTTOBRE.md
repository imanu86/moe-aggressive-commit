# Promozione delle patch validate nel daily Strata — 1 ottobre 2026

Su richiesta dell'utente, le patch validate sono state unite e portate nel lanciatore
operativo del Desktop alle **21:26 Europe/Rome**. La verifica finale usa la cache
**auto/elastica a due zone**, KV int8 **262.144**, residenti **32.768** e riserva di avvio
**1.393 MiB**. Nessuna cache fissa o pressione artificiale in queste due corse.

## Build effettivamente operativa

`D:\ds4_work\strata\Strata\build-0131-daily\strata.exe`, SHA256:
`a74e4dadcd4fbb9e71b5cb0ae66922453c6a44a2704db25ddfb5e81601c5f766`.

Il BAT `Desktop\SERVER IA LOCALE\Strata 2080 Ti - SOTA 30-9 - porta 8100.bat`
usa questo eseguibile tramite il JSON operativo e il server corrispondente in
`build-0131-daily\source\serve\server.py`. Il nome storico del BAT resta lo stesso.
Server SHA256 `3e556df4e13f783f9d961113dd0bbed7481f677e265b45c3a7f238b18530484a`.
Porta 8100 su 127.0.0.1, chiave API ereditata dall'ambiente `STRATA_API_KEY`, mai
letta o salvata. La diagnostica dei logits resta disattivata per impostazione predefinita.

| Componente | Integrazione nel daily |
|---|---|
| Base upstream 0.1.31, `9259cad4cf` | include #242, #258, #270 e decode degli esperti a decodifica unica |
| Nove patch locali, porting 0016 | routing, allineamento checkpoint, elastica, due zone, shrink, banco, pf_parts, commit asincrono |
| 0017 dequantizzazione vettoriale sm75 | stesso oggetto CUDA della variante con 18 controlli bitwise superati |
| 0018 HC/GDN FP16 sm75 | stessa libreria prefill validata sul modello e nel retrieval a 250022 token |
| #315 HC fused | sostituisce la #186 opt-in; mantiene #258 e verifica bitwise sulla scheda prima di usare v3 |
| 0019 primi logits | strumento diagnostico opt-in, non abilitato nel JSON operativo |

Il checkout Git del clone su D: resta `main`, 0.1.30 +13 commit locali. I **sorgenti
completi della build operativa** sono nel suo bundle `build-0131-daily\source`;
ricompilare semplicemente il vecchio checkout produrrebbe un'altra variante.
Eseguibile, PDB, sorgenti, patch combinata e metadati sono conservati nel bundle.

## Validazione finale nel profilo operativo

Tre controlli in questa ripresa: parita' del kernel combinato, riferimento #270,
candidata combinata. Finestra GPU circa **21:15–21:26**; ogni corsa modello ha un
limite totale di 480 secondi. Entrambe completano due riscaldamenti e L01/L02, con
**1024 token generati per richiesta lunga**. La candidata e' stata provata direttamente
nel percorso definitivo su D:, prima di aggiornare il lanciatore.

| Misura | Daily precedente #270 | Nuovo daily combinato |
|---|---:|---:|
| Prefill freddo L01, 131248 token, t/s | 714,58 | **822,66** |
| Primo token L01, s | 184,263 | **160,347** |
| Decode L01, t/s | 40,252 | 41,804 |
| Decode L02, t/s | 35,747 | 36,539 |
| Decode aggregato, t/s | 37,866 | **38,995** |
| Costo aggregato per riga, ms | 22,350 | **22,003** |
| Avvio, s | 65,94 | 46,03 |
| Esperti iniziali, slot | 6215 | 6421 |
| VRAM libera iniziale, MiB | 1216 | 956 |
| CPU altri processi, core medi | 1,19 | 1,16 |
| RAM disponibile minima, GiB | 26,8 | 30,9 |

Prefill **+15,12%**, primo token **23,916 s prima**; decode **+2,98%**, costo per
riga **-1,55%**. E' un singolo confronto dell'intera combinazione: non attribuire
il decode a una sola patch. Numero di esperti e testi/MTP variano; l'elastica mantiene
la stessa policy ma adatta la cache alla VRAM realmente disponibile.
L02 riusa 131072 token e legge solo 167 nuovi: non usarla come misura di prefill freddo.

Il vecchio daily oggi misura 37,9 t/s nello stesso banco: i precedenti 43,9 t/s a
131k furono ottenuti con circa 7273–7574 slot e meno CPU occupata. La riduzione recente
non dimostra una regressione causata dalle patch nuove. Non abbiamo ancora una curva
omogenea contesto/t/s; le prossime misure devono usare questo daily e questa policy.

Il runtime conferma due zone anche nella combinazione: 3184 slot di nucleo, 3237
di coda all'avvio; crescita a 6722 slot, poi riduzione della coda a 6635 sotto il
carico reale. Nessun carico aggiunto per simulare un PC saturo.
Il controllo HC seleziona v3 dopo confronti bitwise a 1–8 token, con/senza pending
write. Il messaggio generico cita cp.async; su sm75 il kernel usa copie ordinarie.

## Limiti della validazione

HC/GDN FP16 cambia l'aritmetica del prefill: non e' bitwise. I controlli precedenti
confermano primi logits finiti, primo token coincidente sui due prompt e recupero
dell'ago a 250022 token; non costituiscono una valutazione generale della qualita'.
Il riempimento a 250k e' stato eseguito sulla variante HC precedente a cache fissa,
non ripetuto in questa combinazione elastica. La nuova verifica prova l'integrazione
operativa a 131k con capacita' KV262144, senza dichiarare superata una prova non eseguita.
Dettagli numerici: `RISULTATI_SERA_HC_FP16_1_OTTOBRE.md`.

## Riproduzione e provenienza

`strumenti/compila_daily_0131.py` ricompila `fused_gr.cu` e `verify.cpp`, ricostruisce
le due librerie e ricollega con gli oggetti/librerie gia' validati. Nessun download.
I percorsi degli input e i loro hash sono in `corse_2080ti/20261001_daily_0131/build/`.
La patch `0020` si applica alla sorgente HC +0019, include 0017 e #315; non applicare
due volte la dequant vettoriale. `git apply --check --ignore-space-change` superato.

```powershell
python -B strumenti/compila_daily_0131.py `
  --base <strata_0131_sm75_20261001> `
  --hc <strata_0131_hc_fp16_20261001> `
  --hc-logits <strata_0131_logits_hc_20261001> `
  --vector <strata_0131_dequant_vec_20261001> `
  --pr315 <strata_pr315_20261001> --out <nuova-cartella>
```

Le sorgenti/input compilati rimangono nel laboratorio locale; porting e compilazione
delle varianti di ingresso sono documentati nei rapporti 0.1.31, #315 e serale HC.
Nel JSON operativo cambia soltanto `exe`; nel BAT cambiano destinazione, server e
commenti. Copie versionate identiche ai file effettivi. Python del BAT e parser
del nuovo server verificati con `--help`, senza riaccendere il modello.
Evidenza delle corse, confronto e manifest di promozione in
`corse_2080ti/20261001_daily_0131/`.

## Ripristino e disponibilita' GPU

Prima della promozione, JSON e BAT reali sono stati copiati in
`D:\ds4_work\strata\ripristini\20261001_212635_0131_daily\`, con manifest e hash.
Per tornare alla #270, chiudere il server e ripristinare quei due file nelle
rispettive destinazioni. L'eseguibile precedente `build-0130-pr270\strata.exe`
e il suo server originale restano disponibili.

Tutti i processi Strata del laboratorio chiusi; nuovo daily lasciato spento.
**VIA esplicito a OCGC-IA e PROMO alle 21:26**, nessun altro job Strata programmato.
Dopo cleanup: 3657 MiB GPU usati, 18574 MiB liberi, utilizzo 14% da carichi desktop
residui. La pubblicazione successiva usa solo CPU.

Regola operativa confermata dall'utente: **patch validata → integrazione nel daily →
prova combinata col profilo operativo → promozione con ripristino**. Le candidate
non devono restare separate dal lanciatore dopo questo passaggio.
