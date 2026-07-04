"""Corpora DIVERSI per testare SPEX su workload reali eterogenei (non solo IT-wiki+BonusX).
Registri: code (avanzato), reasoning/math (CoT), english-prose, + mmlu (conoscenza/ragionamento multi-dominio).
Output /workspace/{code,reasoning,english,mmlu}.jsonl righe {"text": ...}."""
import json
from datasets import load_dataset
def w(path, texts, minlen=200):
    n=0
    with open(path,'w',encoding='utf-8') as f:
        for t in texts:
            t=(t or '').strip()
            if len(t)>=minlen:
                f.write(json.dumps({"text":t[:3200]},ensure_ascii=False)+"\n"); n+=1
    print(path,"->",n, flush=True)
# CODE avanzato: humaneval + mbpp (prompt+soluzione reale)
code=[]
try:
    he=load_dataset("openai_humaneval",split="test"); code+=[r["prompt"]+r["canonical_solution"] for r in he]
except Exception as e: print("humaneval skip",e)
try:
    mb=load_dataset("mbpp",split="train"); code+=[r["text"]+"\n"+r["code"] for r in mb]
except Exception as e: print("mbpp skip",e)
w("/workspace/code.jsonl", code[:220], minlen=120)
# REASONING/MATH: gsm8k question+answer (answer contiene la catena di ragionamento)
try:
    gs=load_dataset("gsm8k","main",split="train"); w("/workspace/reasoning.jsonl",[r["question"]+"\n"+r["answer"] for r in gs][:220])
except Exception as e: print("gsm8k skip",e)
# ENGLISH prosa: wikipedia-en
try:
    en=load_dataset("wikimedia/wikipedia","20231101.en",split="train",streaming=True)
    eng=[]
    for r in en:
        t=(r.get("text") or "").strip()
        if len(t)>=600: eng.append(t[:3200])
        if len(eng)>=200: break
    w("/workspace/english.jsonl", eng)
except Exception as e: print("en-wiki skip",e)
# MMLU: domande di conoscenza multi-dominio (STEM/umanistica/legge/medicina)
try:
    mm=load_dataset("cais/mmlu","all",split="test")
    mmt=[f"{r['question']}\nOptions: {r['choices']}\nAnswer: {r['answer']}" for r in mm]
    w("/workspace/mmlu.jsonl", mmt[:220], minlen=80)
except Exception as e: print("mmlu skip",e)
print("DONE build corpora", flush=True)
