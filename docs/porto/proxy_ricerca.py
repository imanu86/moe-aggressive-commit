"""
PROXY DI RICERCA davanti a llama-server.

llama-server con --jinja sa RENDERE le chiamate a strumento (il modello emette
il blocco tool_calls) ma non ha nessuno che le ESEGUA. Questo proxy chiude
l'anello:

    browser  ->  :8081 (questo)  ->  :8080 (llama-server)
                     |
                     +-- se il modello chiede web_search: esegue la ricerca
                         vera, rimette il risultato in conversazione, richiama

Tutto cio' che non e' /v1/chat/completions passa inalterato, cosi' la WebUI di
llama-server continua a funzionare com'e'.

Uso:  python proxy_ricerca.py       (poi il browser va su :8081, non :8080)
"""

import json, re, sys
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

MONTE = 'http://127.0.0.1:8080'
PORTA = 8081
MAX_GIRI = 4            # quante volte al massimo il modello puo' richiamare uno strumento
MAX_RIS = 6             # risultati per ricerca

app = FastAPI()
cl = httpx.AsyncClient(base_url=MONTE, timeout=None)

STRUMENTI = [{
    "type": "function",
    "function": {
        "name": "web_search",
        "description": ("Cerca sul web informazioni aggiornate o che non conosci. "
                        "Usalo per fatti recenti, versioni di software, notizie, "
                        "documentazione, prezzi. NON usarlo per ragionamenti o codice "
                        "che sai gia' scrivere."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "la ricerca, in parole chiave"}
            },
            "required": ["query"],
        },
    },
}]


def cerca(query: str) -> str:
    try:
        from ddgs import DDGS
        righe = []
        for i, r in enumerate(DDGS().text(query, max_results=MAX_RIS), 1):
            t = (r.get('title') or '').strip()
            u = (r.get('href') or r.get('url') or '').strip()
            c = re.sub(r'\s+', ' ', (r.get('body') or '')).strip()[:400]
            righe.append('[%d] %s\n    %s\n    %s' % (i, t, u, c))
        return ('Risultati per "%s":\n\n' % query) + ('\n\n'.join(righe) if righe else 'nessun risultato')
    except Exception as e:
        return 'ricerca fallita: %s' % e


async def completa(corpo: dict) -> dict:
    r = await cl.post('/v1/chat/completions', json=corpo)
    return r.json()


def sse(testo: str, modello: str):
    """Risposta finale impacchettata come un singolo flusso SSE, cosi' la
    WebUI (che chiede stream=true) la accetta senza modifiche."""
    def gen():
        pezzo = {"id": "proxy", "object": "chat.completion.chunk", "model": modello,
                 "choices": [{"index": 0, "delta": {"role": "assistant", "content": testo},
                              "finish_reason": None}]}
        yield 'data: %s\n\n' % json.dumps(pezzo)
        fine = {"id": "proxy", "object": "chat.completion.chunk", "model": modello,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        yield 'data: %s\n\n' % json.dumps(fine)
        yield 'data: [DONE]\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')


@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat(req: Request):
    corpo = await req.json()
    vuole_flusso = bool(corpo.get('stream'))
    corpo['stream'] = False
    corpo.setdefault('tools', STRUMENTI)
    corpo.setdefault('tool_choice', 'auto')
    messaggi = corpo['messages']

    testo = ''
    for _ in range(MAX_GIRI):
        corpo['messages'] = messaggi
        out = await completa(corpo)
        try:
            msg = out['choices'][0]['message']
        except Exception:
            testo = json.dumps(out)[:2000]
            break
        chiamate = msg.get('tool_calls') or []
        if not chiamate:
            testo = msg.get('content') or ''
            break
        messaggi = messaggi + [msg]
        for c in chiamate:
            try:
                arg = json.loads(c['function'].get('arguments') or '{}')
            except Exception:
                arg = {}
            q = arg.get('query') or arg.get('q') or ''
            print('[ricerca] %s' % q, flush=True)
            messaggi.append({'role': 'tool', 'tool_call_id': c.get('id', ''),
                             'name': c['function'].get('name', 'web_search'),
                             'content': cerca(q)})
    else:
        testo = testo or '(troppi giri di strumento)'

    modello = corpo.get('model', 'ds4')
    if vuole_flusso:
        return sse(testo, modello)
    return Response(json.dumps({
        "id": "proxy", "object": "chat.completion", "model": modello,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": testo},
                     "finish_reason": "stop"}]}), media_type='application/json')


@app.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'])
async def passa(path: str, req: Request):
    """Tutto il resto (WebUI, /health, /props, static) va al server com'e'."""
    dati = await req.body()
    h = {k: v for k, v in req.headers.items() if k.lower() not in ('host', 'content-length')}
    r = await cl.request(req.method, '/' + path, content=dati, headers=h,
                         params=dict(req.query_params))
    hh = {k: v for k, v in r.headers.items()
          if k.lower() not in ('content-length', 'transfer-encoding', 'content-encoding')}
    return Response(content=r.content, status_code=r.status_code, headers=hh)


if __name__ == '__main__':
    import uvicorn
    print('proxy ricerca su http://0.0.0.0:%d  ->  %s' % (PORTA, MONTE))
    uvicorn.run(app, host='0.0.0.0', port=PORTA, log_level='warning')
