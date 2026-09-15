"""P11 - punta il preset W5 ai binari ricompilati (build\\bin invece di bin)."""
import json
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "banco_p0" / "preset_W5_p11.json"
d = json.loads(P.read_text(encoding="utf-8"))
d["binari"] = r"D:\ds4_work\p11_work\build\bin"
dev = [v for v in d.get("deviazioni_dal_lanciatore_quotidiano", [])
       if "copia CONGELATA" not in v]
dev.append(r"binari RICOMPILATI in D:\ds4_work\p11_work\build\bin dallo stesso albero delle celle "
           r"W0-W4 piu' la patch p11 (ubatch a scaletta). Le celle W0-W4 usano la copia congelata "
           r"in D:\ds4_work\p11_work\bin: il confronto W5 contro W4 NON e' a binario invariato, e "
           r"il controllo e' la cadenza dei blocchi iniziali, che deve coincidere con quella di W4.")
d["deviazioni_dal_lanciatore_quotidiano"] = dev
P.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(d["binari"])
print(d["env"]["QWEN_PREFILL_UBATCH_DEEP"])
