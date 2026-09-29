# Strata adattivo — piano del fork (29 settembre 2026)

Obiettivo dell'utente: portare su Strata (MIT, github.com/Niko1221/Strata) quello che abbiamo imparato con DS4 e con
Qwen3.8-Flash-Next, farlo girare molto meglio dell'originale e **tutto adattivo**, e pubblicarne un fork.

Base: il clone `D:\ds4_work\strata\Strata`, main allineato all'originale (0.1.21 del 29/9, storia completa), compilato
con CUDA 12.6 (`build-strata.bat`). Le nostre modifiche vanno sul main del clone come serie di commit piccoli e separati
(per riallinearci all'originale, che cambia ogni giorno), e fino a quando il fork non ha un suo repository le patch sono
copiate e versionate qui, in `patches/`.

## Cosa portiamo, con la prova che ce lo dice

| Da noi | Prova | Su Strata |
|---|---|---|
| Cache esperti elastica sulla VRAM libera (M1/M2/M3/M2g): budget WDDM, crescita solo su budget stabile, restringimento immediato | M2 ferma a 0 slot sotto pressione di RAM → 7,09 t/s; M2g 17,71 (28/9). Strata non si ridimensiona mai dopo l'avvio: lanciato su un picco di VRAM resta a ~700-800 esperti (43-45 ms per riga contro 33) | cache elastica su VMM (base PR #37, corretta sui tre difetti segnalati dal manutentore), senza svuotarla mai |
| Mai svuotare la cache al ridimensionamento; banda morta | M2 svuota tutto a ogni resize (~48 per sessione); M3 +3% a 100k | si escono solo i meno usati (conteggi con decadimento che Strata ha gia') |
| Aritmetica del ciclo di speculazione | 14/9: la bozza 2 perde se la riga di verifica costa troppo | lunghezza della bozza adattiva dal costo misurato per T, non soglia fissa 0,5 |
| Corsia CPU e muro di banda della RAM (DS4: 31-41 GB/s su 40-44; D18) | 29/9: con Jump Desktop e Defender attivi (~3,6 core) Strata costa il 20-30% in piu' | ripartizione CPU/PCIe e numero di thread adattivi alla CPU libera, misurando il tempo delle due vie a ogni finestra |
| Prefill: costo dei follow-up, blocchi e VRAM | 29/9: blocchi da 6.144 → punti di ripresa a 18.432, follow-up 31 s invece di 2 | blocchi allineati ai punti di ripresa (o punti esatti) |
| kvring / doubleKVring (DS4: la RAM bloccata e' la risorsa scarsa, tetto ~76 GiB qui) | Strata tiene gia' tutta la KV in RAM bloccata e in VRAM le pagine lette | 262K con la configurazione; doubleKVring solo se la RAM bloccata diventa il limite |
| doubleKVring esteso alle conversazioni; salvataggio/ripristino degli slot del nostro daily (`--slot-save-path`) | Strata tiene in cache UNA conversazione: passare a un'altra (subagente, chiamata ausiliaria, secondo agente) butta lo stato e fa rileggere tutto (100k token ≈ 4 minuti a ~415 t/s) | cache di piu' conversazioni a livelli: attiva in RAM bloccata, recenti in RAM normale, vecchie su NVMe (1,4 GB ogni 100k token in int8), ripresa senza rilettura. Basi nell'originale: PR #41 (conversazione principale conservata durante le chiamate ausiliarie), PR #52 (KV su NVMe) |
| Metodo | banco deterministico, misura a regime, costo per riga, soglia 5%, punto operativo ~100k | `docs/porto/strata_prova/banco_strata.py`, `costo_passata.py`, profili `regime` e `curva` |

**Fatti del 29/9 sulla 0.1.21** (compilata qui, `strata.exe` A0068A0F): il probe PCIe misura 26,3 GB/s e tiene
`pcie_frac` 0,55; con riserva 1.032 MiB a carico finito restano 151 MiB («LOW: requests may stall», chiede 1.393):
anche la versione nuova occupa VRAM dopo aver dimensionato la cache. Colpi in cache su una richiesta breve di codice in
italiano: **48,9%** con 2.114 esperti (il nostro daily sui casi lunghi: 69-83%). `--calibrate` (0.1.19) misura una volta
tre impostazioni legate all'hardware; non segue la giornata e non tocca il profilo degli esperti.

Ricerca sui fork e sulle novita' dell'originale: `RICERCA_FORK_29_SETTEMBRE.md`. Da li': la cache elastica funzionante
non l'ha fatta nessuno (dalla PR #37 si riusano solo le chiamate VMM); 250K e' gia' dimostrato sul nostro file (fork
RX5950XT: 31,9 t/s a 261K con 16 GB, RAM di picco 78-80 GB); `--prefill 8192` esplicito aggira il difetto dei punti di
ripresa; il layer split della 0.1.21 spegne il KV streaming.

**Patch del fork** (clone, main locale; copie in `patches/`):
- `0001` — la traccia di instradamento (`--dump-routing`) scritta anche nelle finestre di verifica: col server era vuota.

## Ordine

0. **F0 (ore):** profilo degli esperti dal NOSTRO lavoro (italiano, codice, agenti): `--dump-routing` sui nostri prompt
   e `tools/make_profile.py` (pin-by-mass di DS4, +53% sul pod). Misura: colpi in cache e ms per riga col profilo
   originale e col nostro, stessi prompt.
1. **F1 (giorni):** 0.1.21 compilata (fatto); cache elastica VMM che si dimensiona a carico finito e poi di continuo;
   blocchi di prefill allineati. Misure: niente stallo quando gli altri programmi crescono, cache che torna grande quando
   la VRAM si libera, follow-up a 32k in ~2 s.
2. **F2 (giorni):** cache di piu' conversazioni a livelli (RAM bloccata / RAM / NVMe). Misura: tempo al primo token
   quando si torna a una conversazione lunga dopo averne usata un'altra, con Claude Code e dentro DSH (l'utente pensa
   che in un harness come DSH vada gia' meglio: da verificare).
3. **F2b (giorni):** corsia CPU/PCIe adattiva alla CPU libera. Misure con il PC in uso (Jump Desktop acceso) e a riposo.
4. **F3:** speculazione adattiva dai costi misurati.
5. **F4:** 262K; seconda GPU (2080 Ti) col layer split della 0.1.21 e la cache elastica per GPU.

Ogni passo: A/B col profilo `regime` contro la versione senza la modifica, stesso momento della giornata, VRAM e CPU
degli altri programmi registrate; si tiene solo sopra il 5% (o se toglie un guasto).

## Pubblicazione

MIT: si tengono LICENSE e crediti, nome diverso. Creare il repository pubblico e' un'azione verso l'esterno: si chiede
all'utente prima. In parallelo, le parti piccole e misurate si possono proporre all'originale come PR (il manutentore le
accetta con misura prima/dopo): piu' utenti, meno manutenzione del fork.
