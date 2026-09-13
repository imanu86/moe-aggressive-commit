"""Prova REALE di qualita' su contesto lungo (v2).

Il rischio proprio dell'attenzione sparsa e' perdere cio' che sta fuori dalle
celle scelte dal top-k: il modello resta fluente ma ragiona su un contesto
amputato, e un banco di soli token al secondo non lo vedrebbe.

v2 corregge tre difetti della v1:
  - salvava solo `content`, e con --reasoning on il modello mette tutto in
    `reasoning_content`: le risposte stampate erano vuote;
  - 120 token di budget potevano finire dentro il ragionamento, producendo un
    falso "perso" per troncamento invece che per contesto perduto;
  - tre aghi soli. Il prefill si paga UNA volta (le domande successive vanno a
    cache), quindi aggiungerne non costa quasi nulla.

Uso:  python prova_reale.py --ctx-tokens 131072 --label sfa1
"""
import argparse, json, pathlib, re, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument('--url', default='http://127.0.0.1:8100')
ap.add_argument('--ctx-tokens', type=int, default=131072)
ap.add_argument('--label', required=True)
ap.add_argument('--max-tokens', type=int, default=400)
args = ap.parse_args()

HERE = pathlib.Path(__file__).parent
bat = pathlib.Path(r'C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat').read_text(errors='replace')
KEY = re.search(r'set "API_KEY=([^"]*)"', bat).group(1)
H = {'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + KEY}


def post(path, body, timeout=10800):
    req = urllib.request.Request(args.url + path, data=json.dumps(body).encode('utf-8'), headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def chiedi(messages, max_tokens):
    body = {'messages': messages, 'max_tokens': max_tokens, 'stream': True,
            'stream_options': {'include_usage': True}, 'temperature': 0}
    req = urllib.request.Request(args.url + '/v1/chat/completions',
                                 data=json.dumps(body).encode('utf-8'), headers=H)
    t0 = time.perf_counter()
    testo, ragion, timings = [], [], None
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
                testo.append(d.get('content') or '')
                ragion.append(d.get('reasoning_content') or '')
    t = ''.join(testo).strip()
    rg = ''.join(ragion).strip()
    n_gen = (timings or {}).get('predicted_n', 0)
    return {
        'testo': t,
        'ragionamento': rg,
        'n_gen': n_gen,
        'troncato': bool(n_gen and n_gen >= max_tokens),   # ha esaurito il budget
        'mostrato': t if t else ('[solo ragionamento] ' + rg[-500:]),
        'dt': round(time.perf_counter() - t0, 1),
    }


# ---- aghi: stringhe DISTINTIVE, che non devono esistere nel materiale -------
AGHI = [
    (0.05, "NOTA OPERATIVA ALFA: il codice di collaudo del banco ALFA e' MANDORLA-417.",
     "Qual e' il codice di collaudo del banco ALFA? Rispondi con il solo codice.", "MANDORLA-417"),
    (0.25, "NOTA OPERATIVA BETA: il colore di segnalazione del banco BETA e' VIOLA-CENERE.",
     "Qual e' il colore di segnalazione del banco BETA? Rispondi con la sola parola.", "VIOLA-CENERE"),
    (0.50, "NOTA OPERATIVA GAMMA: il responsabile del banco GAMMA e' Ferruccio Malinverni.",
     "Chi e' il responsabile del banco GAMMA? Rispondi con il solo cognome.", "Malinverni"),
    (0.75, "NOTA OPERATIVA DELTA: il numero di serie del banco DELTA e' ZR-8842.",
     "Qual e' il numero di serie del banco DELTA? Rispondi con il solo numero.", "ZR-8842"),
    (0.95, "NOTA OPERATIVA EPSILON: la parola d'ordine del banco EPSILON e' TRAMONTANA.",
     "Qual e' la parola d'ordine del banco EPSILON? Rispondi con la sola parola.", "TRAMONTANA"),
]

src = pathlib.Path(r'C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source')
parti, n = [], 0
for p in sorted(x for x in src.rglob('*')
                if x.is_file() and x.suffix in ('.cpp', '.c', '.h', '.cu', '.cuh', '.py')
                and 'build' not in x.parts and x.stat().st_size < 400_000):
    parti.append(f'// ===== FILE {p.relative_to(src)} =====\n{p.read_text(encoding="utf-8", errors="replace")}')
    n += len(parti[-1])
    if n > args.ctx_tokens * 3.6:
        break
testo_base = '\n'.join(parti)

tok = post('/tokenize', {'content': testo_base})['tokens']
if len(tok) > args.ctx_tokens:
    testo_base = post('/detokenize', {'tokens': tok[:args.ctx_tokens]})['content']
    tok = tok[:args.ctx_tokens]
print(f'contesto: {len(tok)} token', flush=True)

# se un atteso esistesse gia' nel materiale, "trovato" non proverebbe nulla
for _, _, _, atteso in AGHI:
    if atteso.lower() in testo_base.lower():
        print(f'  ATTENZIONE: "{atteso}" compare gia\' nel materiale: ago inutilizzabile', flush=True)

pezzi, ultimo = [], 0
for frazione, ago, _, _ in AGHI:
    taglio = int(len(testo_base) * frazione)
    pezzi.append(testo_base[ultimo:taglio])
    pezzi.append(f'\n\n// {ago}\n\n')
    ultimo = taglio
pezzi.append(testo_base[ultimo:])
contesto = ''.join(pezzi)

base = [
    {'role': 'user', 'content': 'Leggi con attenzione il materiale seguente e rispondi soltanto "pronto".\n\n' + contesto},
    {'role': 'assistant', 'content': 'pronto'},
]

esiti = []
for frazione, _, domanda, atteso in AGHI:
    r = chiedi(base + [{'role': 'user', 'content': domanda}], args.max_tokens)
    trovato = atteso.lower() in (r['testo'] + r['ragionamento']).lower()
    r.update({'tipo': 'ago', 'profondita': frazione, 'domanda': domanda,
              'atteso': atteso, 'trovato': trovato})
    esiti.append(r)
    stato = 'TROVATO' if trovato else ('PERSO(troncato)' if r['troncato'] else 'PERSO')
    print(f'  ago a {int(frazione*100):>3}%  {stato:<16} {r["n_gen"]:>4} token, {r["dt"]:>6}s  '
          f'-> {r["mostrato"][:150]}', flush=True)

DOMANDA_TECNICA = (
    "Nel codice che ti ho dato, quale funzione decide a RUNTIME se usare la flash attention "
    "sparsa, e quali condizioni impone? Rispondi in italiano, citando il nome della funzione "
    "e le condizioni principali."
)
r = chiedi(base + [{'role': 'user', 'content': DOMANDA_TECNICA}], args.max_tokens)
r.update({'tipo': 'tecnica', 'domanda': DOMANDA_TECNICA})
esiti.append(r)
print(f'\n--- domanda tecnica ({r["dt"]}s, {r["n_gen"]} token):\n{r["mostrato"]}\n', flush=True)

out = HERE / f'prova_reale_{args.label}.json'
out.write_text(json.dumps({'label': args.label, 'ctx': len(tok), 'esiti': esiti},
                          ensure_ascii=False, indent=2), encoding='utf-8')
n_ok = sum(1 for e in esiti if e.get('trovato'))
print(f'aghi trovati: {n_ok}/{len(AGHI)}   salvato in {out.name}')
