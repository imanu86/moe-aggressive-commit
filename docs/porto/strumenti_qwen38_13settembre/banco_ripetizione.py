"""Banco a RIPETIZIONE: il carico dove gli speculatori a n-grammi possono agganciare.

Motivo. Gli n-grammi abbozzano ripescando sequenze gia' viste nel prompt. Sulle
domande generiche del banco normale ("spiega come funziona una cache LRU") non
agganciano quasi mai, e misurarli li' vuol dire misurare il nulla. Il carico
realistico del harness e' invece un assistente di codice che RIPRODUCE pezzi del
file che gli hai dato: la' l'n-grammo ha materiale.

Da ricordare leggendo i risultati: gli n-grammi hanno PRECEDENZA sulla testa MTP
(speculative.cpp:2672-2684) e la scavalcano ogni volta che agganciano. Quindi la
combinazione conviene solo se l'n-grammo, quando spara, accetta piu' dello 0,75
della testa. L'attribuzione per implementatore la stampa il server a ogni
richiesta, subito dopo la riga "draft acceptance" (server-context.cpp:713).

Uso:
    python banco_ripetizione.py --label mtp_solo
    python banco_ripetizione.py --label mtp_piu_ngram
"""
import argparse, json, pathlib, re, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://127.0.0.1:8100')
ap.add_argument('--label', required=True)
ap.add_argument('--file', default=r'C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source\ggml\src\ggml-cuda\moe-demand.cuh',
                help='file da far riprodurre: deve stare comodamente nel contesto')
ap.add_argument('--max-tokens', type=int, default=1600)
ap.add_argument('--turns', type=int, default=2)
args = ap.parse_args()

HERE = pathlib.Path(__file__).parent
bat = pathlib.Path(r'C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat').read_text(errors='replace')
KEY = re.search(r'set "API_KEY=([^"]*)"', bat).group(1)
H = {'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + KEY}

sorgente = pathlib.Path(args.file).read_text(encoding='utf-8', errors='replace')
print(f'file: {pathlib.Path(args.file).name}, {len(sorgente)} caratteri', flush=True)

# Due compiti a ripetizione crescente: il primo copia quasi tutto, il secondo copia
# con una trasformazione meccanica. In entrambi l'uscita e' in gran parte gia' nel prompt.
COMPITI = [
    ("Riscrivi INTEGRALMENTE il file seguente senza modificarlo, riga per riga. "
     "Non aggiungere commenti, non spiegare nulla, restituisci soltanto il codice.\n\n```\n"
     + sorgente + "\n```"),
    ("Riscrivi INTEGRALMENTE il file seguente sostituendo ovunque l'identificatore "
     "`bound_group` con `gruppo_legato`. Lascia tutto il resto invariato, riga per riga. "
     "Non spiegare nulla, restituisci soltanto il codice.\n\n```\n" + sorgente + "\n```"),
]


def corsa(messaggi, etichetta):
    body = {'messages': messaggi, 'max_tokens': args.max_tokens, 'stream': True,
            'stream_options': {'include_usage': True}, 'temperature': 0}
    req = urllib.request.Request(args.url + '/v1/chat/completions',
                                 data=json.dumps(body).encode('utf-8'), headers=H)
    t0 = time.perf_counter()
    pezzi, ragion, timings = [], [], None
    with urllib.request.urlopen(req, timeout=10800) as r:
        for raw in r:
            line = raw.decode('utf-8', errors='replace').strip()
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            o = json.loads(data)
            if o.get('timings'):
                timings = o['timings']
            for ch in o.get('choices', []):
                d = ch.get('delta', {})
                pezzi.append(d.get('content') or '')
                ragion.append(d.get('reasoning_content') or '')
    tm = timings or {}
    uscita = ''.join(pezzi)
    # quanto dell'uscita e' davvero copiato dal prompt: e' cio' che l'n-grammo puo' agganciare
    righe = [r for r in uscita.splitlines() if len(r.strip()) > 12]
    copiate = sum(1 for r in righe if r.strip() in sorgente)
    rec = {
        'label': args.label, 'compito': etichetta,
        'wall_s': round(time.perf_counter() - t0, 3),
        'gen_n': tm.get('predicted_n'), 'gen_tps': round(tm.get('predicted_per_second', 0), 2),
        'prompt_n': tm.get('prompt_n'), 'prompt_tps': round(tm.get('prompt_per_second', 0), 2),
        'draft_n': tm.get('draft_n'), 'draft_n_accepted': tm.get('draft_n_accepted'),
        'righe_uscita': len(righe), 'righe_copiate': copiate,
        'quota_copiata': round(copiate / len(righe), 3) if righe else 0.0,
    }
    if rec['draft_n']:
        rec['accettazione'] = round(rec['draft_n_accepted'] / rec['draft_n'], 4)
    print(json.dumps(rec), flush=True)
    return rec, uscita


risultati = []
for i, compito in enumerate(COMPITI[:args.turns]):
    rec, uscita = corsa([{'role': 'user', 'content': compito}], f'compito{i+1}')
    (HERE / f'ripetizione_{args.label}_c{i+1}.txt').write_text(uscita, encoding='utf-8')
    risultati.append(rec)

out = HERE / f'ripetizione_{args.label}.json'
out.write_text(json.dumps(risultati, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nsalvato in {out.name}')
print('Ora leggere nel log del server, dopo "draft acceptance", le statistiche per')
print('implementatore: dicono QUANTE bozze ha prodotto ciascuno e quanto e\' costato.')
