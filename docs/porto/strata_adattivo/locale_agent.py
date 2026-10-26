"""locale_agent.py - lancia un agente di lavoro (Claude Agent SDK) che gira sul NOSTRO motore Strata (porta 8100), non su Anthropic.

    python locale_agent.py --brief brief.md --cwd C:\\Users\\imanu\\source\\repos\\Strata-wt\\<worktree> [--log out.jsonl]

Il server Strata deve essere acceso su 127.0.0.1:8100 (config D:\\ds4_work\\strata\\Strata\\strata-0145-agenti.json).
Nessuna chiave Anthropic: ANTHROPIC_BASE_URL punta a Strata, la chiave è quella del server (STRATA_API_KEY se impostata,
altrimenti un segnaposto). Il costo in dollari riportato dall'SDK non ha senso qui: conta solo il numero di turni.
Più agenti lanciati insieme = prova reale del multichat del motore.
"""
import argparse, asyncio, json, os, time
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="file con il compito completo")
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--model", default="strata")
    ap.add_argument("--max-turns", type=int, default=300)
    ap.add_argument("--log", default=None)
    ap.add_argument("--max-resumes", type=int, default=20)
    a = ap.parse_args()
    brief = Path(a.brief).read_text(encoding="utf-8")
    log = Path(a.log or (Path(a.brief).with_suffix(".log.jsonl")))
    opts = ClaudeAgentOptions(
        model=a.model, cwd=a.cwd, max_turns=a.max_turns,
        permission_mode="bypassPermissions", max_buffer_size=64 * 2**20,
        # 26/10: elenco tool fisso e niente MCP, così il prefisso (tools prima del system) è uguale a ogni turno
        # e la cache del motore lo riusa (DIAGNOSI.md in corse_2080ti/20261026_cache_prompt).
        tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
        extra_args={"strict-mcp-config": None},
        env={"ANTHROPIC_BASE_URL": a.url,
             "ANTHROPIC_API_KEY": os.environ.get("STRATA_API_KEY") or "locale",
             "ANTHROPIC_SMALL_FAST_MODEL": a.model,
             "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
             "HTTPS_PROXY": "", "NODE_EXTRA_CA_CERTS": ""},
    )
    rules = ("\n\nREGOLA DEL LANCIATORE: qui non ricevi notifiche dei comandi in background. Per aspettare usa un ciclo "
             "che controlla la condizione (until ...; do sleep 30; done) dentro lo stesso comando, mai chiudere il turno "
             "per aspettare. NON fermare né riavviare strata.exe sulla porta 8100: è il motore su cui giri tu. "
             "Quando hai finito davvero, l'ultima riga del report deve essere esattamente: FINE LAVORO")
    t0, prompt, sid = time.time(), brief + rules, None
    with log.open("a", encoding="utf-8") as f:
        for giro in range(a.max_resumes + 1):
            if sid:
                opts.resume = sid
            done = False
            try:
              async for m in query(prompt=prompt, options=opts):
                kind = type(m).__name__
                if kind == "SystemMessage" and not sid:
                    sid = (getattr(m, "data", {}) or {}).get("session_id") or sid
                rec = {"t": round(time.time() - t0, 1), "kind": kind, "giro": giro}
                if kind == "AssistantMessage":
                    rec["text"] = " ".join(getattr(b, "text", "") for b in m.content if hasattr(b, "text"))[:2000]
                elif kind == "ResultMessage":
                    sid = m.session_id
                    done = "FINE LAVORO" in (m.result or "")
                    rec.update(result=(m.result or "")[:20000], is_error=m.is_error, turns=m.num_turns)
                    print(json.dumps(rec, ensure_ascii=False)[:4000], flush=True)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            except Exception as e:
                f.write(json.dumps({"t": round(time.time() - t0, 1), "kind": "ERRORE", "giro": giro, "err": str(e)[:500]}) + "\n")
                f.flush()
            if done:
                break
            prompt = ("Continua il lavoro da dove eri: controlla lo stato dei comandi che avevi lanciato (log, processi) "
                      "e prosegui. A lavoro finito chiudi con FINE LAVORO.")


asyncio.run(main())
