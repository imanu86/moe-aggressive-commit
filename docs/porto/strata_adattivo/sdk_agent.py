"""sdk_agent.py - lancia un agente di lavoro (Claude Agent SDK) pagato coi crediti API, non col piano Max.

    python sdk_agent.py --brief brief.md --cwd C:\\Users\\imanu\\source\\repos\\Strata-wt\\<worktree> --budget 30 [--log out.jsonl]

La chiave e il workspace si leggono dal registro utente (HKCU\\Environment):
  STRATA_SDK_API_KEY       chiave «strata» (ambito Organizzazione), mai stampata
  STRATA_SDK_WORKSPACE_ID  workspace Default (header anthropic-workspace-id obbligatorio)
Non esportare mai la chiave come ANTHROPIC_API_KEY globale: Claude Code fatturerebbe le sue sessioni sull'API.
Il brief deve contenere le regole del laboratorio (lock GPU, build_lock, niente Daily, commit OPUS-STRATA, stato nel doc).
--budget è un tetto rigido in dollari (max_budget_usd dell'SDK). Crediti: 200 $ fino al 17/10/2026, condivisi.
"""
import argparse, asyncio, json, time, winreg
from pathlib import Path
from claude_agent_sdk import query, ClaudeAgentOptions


def reg(name):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        return winreg.QueryValueEx(k, name)[0]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="file con il compito completo")
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--budget", type=float, required=True, help="tetto in dollari")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-turns", type=int, default=400)
    ap.add_argument("--log", default=None)
    ap.add_argument("--max-resumes", type=int, default=20, help="riprese della sessione se l'agente si ferma prima")
    a = ap.parse_args()
    brief = Path(a.brief).read_text(encoding="utf-8")
    log = Path(a.log or (Path(a.brief).with_suffix(".log.jsonl")))
    opts = ClaudeAgentOptions(
        model=a.model, effort=a.effort, cwd=a.cwd, max_turns=a.max_turns, max_budget_usd=a.budget,
        permission_mode="bypassPermissions",
        allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch"],
        env={"ANTHROPIC_API_KEY": reg("STRATA_SDK_API_KEY"),
             "ANTHROPIC_CUSTOM_HEADERS": "anthropic-workspace-id: " + reg("STRATA_SDK_WORKSPACE_ID")},
    )
    # Una sessione SDK finisce quando l'agente chiude il turno: qui non arrivano notifiche dei comandi in background.
    # Si riprende la stessa sessione finché il risultato non contiene FINE LAVORO o finisce il budget.
    rules = ("\n\nREGOLA DEL LANCIATORE: qui non ricevi notifiche dei comandi in background. Per aspettare usa un ciclo "
             "che controlla la condizione (until ...; do sleep 30; done) dentro lo stesso comando, mai chiudere il turno "
             "per aspettare. Quando hai finito davvero, l'ultima riga del report deve essere esattamente: FINE LAVORO")
    t0, spent, prompt, sid = time.time(), 0.0, brief + rules, None
    with log.open("a", encoding="utf-8") as f:
        for giro in range(a.max_resumes + 1):
            if sid:
                opts.resume = sid
            opts.max_budget_usd = max(0.5, a.budget - spent)
            done = False
            async for m in query(prompt=prompt, options=opts):
                kind = type(m).__name__
                rec = {"t": round(time.time() - t0, 1), "kind": kind, "giro": giro}
                if kind == "AssistantMessage":
                    rec["text"] = " ".join(getattr(b, "text", "") for b in m.content if hasattr(b, "text"))[:2000]
                elif kind == "ResultMessage":
                    spent += m.total_cost_usd or 0.0
                    sid = m.session_id
                    done = "FINE LAVORO" in (m.result or "")
                    rec.update(result=(m.result or "")[:20000], cost_usd=m.total_cost_usd, spent=round(spent, 2),
                               is_error=m.is_error, turns=m.num_turns)
                    print(json.dumps(rec, ensure_ascii=False)[:4000], flush=True)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            if done or spent >= a.budget - 0.5:
                break
            prompt = ("Continua il lavoro da dove eri: controlla lo stato dei comandi che avevi lanciato (log, processi, "
                      "lock) e prosegui. Ricorda: niente turni chiusi per aspettare; a lavoro finito chiudi con FINE LAVORO.")


asyncio.run(main())
