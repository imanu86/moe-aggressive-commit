"""Un prompt di almeno 250000 token reali, col tokenizer del modello e un ago al 50%."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

from compila_0131 import BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--tokenizer", type=Path, required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if "STRATA_API_KEY" in os.environ: raise RuntimeError("Escludere STRATA_API_KEY")
    if not a.url.startswith("http://127.0.0.1:"): raise RuntimeError("Solo server loopback")
    sys.path.insert(0, str(BASE / ".venv/Lib/site-packages"))
    sys.path.insert(0, str(a.source / "tools"))
    sys.path.insert(0, str(a.source))
    import strata_tokenizer as ST
    from serve.frontend import ChatTemplate
    vocab = json.loads((a.tokenizer / "vocab.json").read_text(encoding="utf-8"))
    tokens = [None]*len(vocab)
    for text, i in vocab.items(): tokens[i] = text
    tok = ST.Tokenizer(tokens, (a.tokenizer / "merges.txt").read_text(encoding="utf-8").split("\n"),
                       json.loads((a.tokenizer / "token_type.json").read_text(encoding="utf-8")))
    template = ChatTemplate(a.tokenizer / "chat_template.jinja")
    filler_path = Path(__file__).resolve().parents[2] / "banco_p0/fixtures/filler_sorgenti_20260914.txt"
    filler = filler_path.read_text(encoding="utf-8")
    word = "ARCO-AMBRA-742913"
    assert word not in filler
    pool = filler*4
    def prompt(chars):
        text = pool[:chars]
        cut = text.rfind("\n",0,len(text)//2)+1
        needle = f"\nThe secret code word for this text is: {word}. Remember it.\n"
        return text[:cut]+needle+text[cut:]+"\n\nWhat is the secret code word mentioned above? Reply with the code word only."
    lo, hi = 0, len(pool)
    count = 0
    while lo < hi:
        mid = (lo+hi)//2
        content = prompt(mid)
        rendered = template.render([{"role":"user","content":content}], enable_thinking=False)
        count = len(tok.encode(rendered, parse_special=True))
        if 250000 <= count <= 250063: break
        if count < 250000: lo = mid+1
        else: hi = mid
    if not 250000 <= count <= 250063: raise RuntimeError("Impossibile dimensionare il prompt: " + str(count))
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / "prompt.txt").write_text(content, encoding="utf-8")
    result = {"target_tokens":250000,"local_tokens":count,"needle_depth":50,"word":word,
        "prompt_sha256":hashlib.sha256(content.encode()).hexdigest(),"filler_sha256":hashlib.sha256(filler.encode()).hexdigest(),
        "filler_characters":mid,"max_tokens":40,"artificial_load":False}
    (a.out / "result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("PROMPT_READY",count,"tokens",flush=True)
    data={"model":"strata","max_tokens":40,"temperature":0,"chat_template_kwargs":{"enable_thinking":False},
          "messages":[{"role":"user","content":content}]}
    req=urllib.request.Request(a.url+"/v1/chat/completions",data=json.dumps(data).encode(),headers={"Content-Type":"application/json"})
    start=time.monotonic()
    with urllib.request.urlopen(req,timeout=1800) as response: answer=json.load(response)
    result.update(seconds=round(time.monotonic()-start,2),usage=answer["usage"],answer=answer["choices"][0]["message"].get("content") or "")
    result["found"]=word in result["answer"]
    result["capacity_validated"]=250000 <= result["usage"]["prompt_tokens"] <= 250063
    with urllib.request.urlopen(a.url+"/metrics",timeout=10) as response: result["metrics"]=json.load(response)
    (a.out / "result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "metrics"}),flush=True)
    if not result["capacity_validated"] or not result["found"]: raise RuntimeError("Controllo 250k fallito")


if __name__ == "__main__": main()
