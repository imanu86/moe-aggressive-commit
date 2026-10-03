# PR512: integrazione upstream e ripetizione del 3 ottobre 2026

La patch top-k è stata integrata manualmente nella release upstream 0.1.38, autore imanu86,
commit [474a94b](https://github.com/Niko1221/Strata/commit/474a94bfdc68dc1ef473b7d9df50521b253e04e4),
con Co-Authored-By Codex. Il [commento del maintainer](https://github.com/Niko1221/Strata/pull/512#issuecomment-5964019532)
spiega perché GitHub non presenta la PR come merged. Il successivo flag STRATA_TOPK_ACTIVE_ANY=1 permette
al test di attivare il percorso anche su altre GPU; non cambia il default Turing del motore.

Alla verifica finale la PR è **closed, draft=true, merged=false**: l'integrazione è manuale e già rilasciata,
quindi non c'è una revisione ancora in attesa. Il rapporto e l'handoff sono aggiornati soltanto localmente:
git add è stato rifiutato con `.git/index.lock: Permission denied`; nessun nuovo commit/push né modifica della PR.

## Ripetizione isolata

Aggiornamento pubblicazione 3 ottobre: accesso completo ripristinato; report,
53 evidenze verificate tramite manifest e handoff pubblicati sul branch research.
Il rifiuto di scrittura sopra è storico. Nessun nuovo commento alla PR512:
su richiesta dell'utente, ulteriori proposte aspettano misure specifiche concluse.

RTX2080Ti modificata22GB, Ryzen5800X,96GB RAM,Windows,CUDA12.6. **Stesso eseguibile della prova precedente:**
upstream0.1.37 db4f91a1171d697928b0d2e1f50ef95e25559d4c più le sole quattro modifiche della PR512.
Questa ripetizione non è una build completa0.1.38. SHA256 motore: `9933918a7f1e6dee2e55b41552df068e654169834c7d6e7679710330469b5207`.

Capacità/attivi/capacità A/B/A; KV262144 int8, resident32768; PCIe0.28, prefillauto,
spec4 con lookup3, stesso profilo esperti; cache fissa budget4000, **5357 slot effettivi** in tutte le braccia.
Nessuna elasticità e nessun carico artificiale. CUDA cache condivisa tra le braccia.
Due output da1024 token per braccio: prompt fresco131248 e follow-up131239 con131072 token riusati.

| Percorso | Prefill fresco t/s | TTFT s | Decode aggregato t/s |
|---|---:|---:|---:|
| Capacità A1 | 776.53 | 169.628 | 39.640 |
| Attivi B | 832.24 | 158.325 | 39.133 |
| Capacità A2 | 772.34 | 170.675 | 39.669 |

**Prefill +7.46%** sulla media dei riferimenti; spread dei riferimenti
**0.54%**. TTFT ridotto di **11.83s**.
Guadagno osservato in questo A/B/A; nessun guadagno decode attribuito alla patch.
Parità del kernel: **16/16**, ID selezionati identici bit per bit. Sei richieste lunghe completate.
Il corpus dei tempi non contiene un nuovo oracle numerico dell'intero modello e non dimostra qualità generale.

## Controllo dei carichi

Monitor circa ogni10s: CPU totale/per-thread, processi, RAM libera, I/O disco, GPU/VRAM/clock/temperatura.
Le finestre prefill sono derivate da `history.time = started` nel server e da prompt_ms: 15/14/15 campioni.
Durante i prefill: RAM libera almeno21.3GiB, VRAM nvidia-smi3269MiB libera, GPU quasi sempre99–100%,
CPU totale17.7–25.6%, altro CPU incluse le utility della prova al massimo7.3% della macchina.
Clock memoria6800MHz; medianaSM1815/1777.5/1785MHz, massimo65°C. Non è stata osservata saturazione globale
esterna nei campioni; un contatore GPU aggregato non separa ogni applicazione. I/O lettura mediano
42.7/25.5/23.3MiB/s, inclusa la lettura PLE del modello; non è una misura isolata del disco delle altre app.
Le misure precedenti457.26/521.45/774.41 restano conservate e inconcludenti: questa ripetizione
non identifica retroattivamente la causa dei valori bassi.

## Contributi ulteriori

- **Cache elastica:** API CUDA VMM open_sized_elastic/grow/shrink, indirizzi stabili per i graph,
  margine VRAM e isteresi, core stabile e coda ridimensionabile. Presente nel nostro fork, assente
  dalle API expert_cache e dall'opzione --elastic in generate.cpp della0.1.38 controllata.
  Candidato concreto per una PR separata; serve un port minimo su upstream e una verifica specifica
  di crescita/riduzione, dati degli esperti, fallback e sincronizzazione. Nessuna pressione artificiale richiesta.
- **Strumenti di parità e benchmark riproducibili:** riutilizzabili per valutare cache e kernel.
- HC/GDN FP16 e vector dequant provengono da jklnvlink: preservare l'attribuzione; non presentarli come invenzioni nostre.
- Il top-k dinamico decode sperimentale non ha superato il gate prestazionale: non proporlo come guadagno confermato.

**Nessuna nuova SOTA del Daily:** questa è una prova upstream con cache fissa e senza gli altri port Turing.
Il Daily operativo resta invariato. Motori chiusi; RAM libera finale67.9GiB.

Evidenze locali: [manifest](corse_2080ti/20261003_pr512_ripetizione/manifest.json),
[analisi](corse_2080ti/20261003_pr512_ripetizione/analysis.json),
[confronto completo](corse_2080ti/20261003_pr512_ripetizione/comparison.json),
[risorse](corse_2080ti/20261003_pr512_ripetizione/resources.jsonl).
