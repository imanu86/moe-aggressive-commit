"""Two concurrent greedy requests to the running 8100 server (sanity check of --batch / --batch-mtp before the agents).
Outputs are data; never execute model text."""
import json, sys, threading, time

import agente as A

Q = ["Scrivi una funzione Python che restituisce i numeri primi minori di n, con un breve commento.",
     "Spiega in dieci righe come funziona una tabella hash e cosa succede alle collisioni."]
res = {}


def one(i):
    t0 = time.monotonic()
    try:
        r = A.get('/v1/chat/completions', dict(model=sys.argv[1] if len(sys.argv) > 1 else 'strata', temperature=0,
                                               max_tokens=400, messages=[dict(role='user', content=Q[i])],
                                               chat_template_kwargs=dict(enable_thinking=False)), timeout=900)
        res[i] = dict(ok=True, s=round(time.monotonic() - t0, 1), usage=r.get('usage'),
                      head=r['choices'][0]['message']['content'][:120])
    except Exception as e:   # noqa: BLE001
        res[i] = dict(ok=False, s=round(time.monotonic() - t0, 1), err=repr(e)[:300])


th = [threading.Thread(target=one, args=(i,)) for i in range(2)]
for t in th:
    t.start()
for t in th:
    t.join()
print(json.dumps(res, ensure_ascii=False, indent=1))
