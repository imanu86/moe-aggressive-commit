"""Reverse proxy 8106 -> 8100: salva il solo corpo JSON di ogni POST /v1/messages (niente header) e inoltra tutto intatto, streaming compreso."""
import asyncio, json, sys
from pathlib import Path
import aiohttp
from aiohttp import web

UP = "http://127.0.0.1:8100"
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
n = [len(list(OUT.glob("req_*.json")))]
HOP = {"host", "content-length", "transfer-encoding", "connection"}

async def handle(req: web.Request):
    body = await req.read()
    if req.method == "POST" and req.path.startswith("/v1/messages") and "count_tokens" not in req.path:
        try:
            (OUT / f"req_{n[0]:03d}.json").write_text(json.dumps(json.loads(body), ensure_ascii=False, indent=1), encoding="utf-8")
            n[0] += 1
        except Exception as e:
            print("save err", e, flush=True)
    h = {k: v for k, v in req.headers.items() if k.lower() not in HOP}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None)) as s:
        async with s.request(req.method, UP + req.path_qs, data=body, headers=h) as r:
            resp = web.StreamResponse(status=r.status, headers={k: v for k, v in r.headers.items() if k.lower() not in HOP})
            await resp.prepare(req)
            async for chunk in r.content.iter_any():
                await resp.write(chunk)
            await resp.write_eof()
            return resp

app = web.Application(client_max_size=256 * 2**20)
app.router.add_route("*", "/{tail:.*}", handle)
web.run_app(app, host="127.0.0.1", port=8106, print=None)
