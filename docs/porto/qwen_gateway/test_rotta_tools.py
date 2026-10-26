"""Test dell'elenco tool stabile per conversazione (rotta_locale.pulisci). Senza rete:  python test_rotta_tools.py"""
from __future__ import annotations
import json
import rotta_locale as r


def tool(nome: str, **extra) -> dict:
    return {"name": nome, "description": "d " + nome, "input_schema": {"type": "object", "properties": {}}, **extra}


def richiesta(tools: list[dict], sid: str = "aaaa-1111", turni: int = 1, prima: str = "Ciao") -> dict:
    msgs = [{"role": "user", "content": prima}]
    for i in range(turni - 1):
        msgs += [{"role": "assistant", "content": f"r{i}"}, {"role": "user", "content": f"u{i}"}]
    return {"model": "claude-haiku-4-5", "stream": True, "max_tokens": 10,
            "system": [{"type": "text", "text": "x-anthropic-billing-header: cch=" + str(turni)}, {"type": "text", "text": "Sei Claude Code."}],
            "metadata": {"user_id": "user_x_account_y_session_" + sid}, "messages": msgs, "tools": tools}


def nomi(j: dict) -> list[str]:
    return [t["name"] for t in r.pulisci(j)["tools"]]


def main() -> None:
    r._tools_visti.clear()
    # 3 turni: un tool compare in mezzo (MCP connesso dopo), uno sparisce, uno defer_loading viene caricato dopo.
    t1 = nomi(richiesta([tool("Read"), tool("Bash"), tool("Mcp", defer_loading=True)], turni=1))
    t2 = nomi(richiesta([tool("Read"), tool("mcp__a"), tool("Bash"), tool("Mcp", defer_loading=True)], turni=2))
    t3 = nomi(richiesta([tool("mcp__a"), tool("Read"), tool("Mcp"), tool("mcp__b")], turni=3))
    assert t1 == ["Read", "Bash"], t1
    assert t2 == ["Read", "Bash", "mcp__a"], t2          # nuovo in coda, ordine di prima apparizione
    assert t3 == ["Read", "Bash", "mcp__a", "Mcp", "mcp__b"], t3  # Bash sparito ma resta; Mcp senza defer entra in coda
    for a, b in ((t1, t2), (t2, t3)):
        assert b[:len(a)] == a                          # il prefisso non cambia, si cresce solo in coda
    # il prefisso serializzato (cio' che il template mette per primo) resta byte-identico
    j1 = json.dumps(r.pulisci(richiesta([tool("Read")], sid="s2"))["tools"])[:-1]
    j2 = json.dumps(r.pulisci(richiesta([tool("Read"), tool("Nuovo")], sid="s2", turni=2))["tools"])
    assert j2.startswith(j1)
    # il defer_loading non ancora caricato resta escluso
    assert "Mcp" not in nomi(richiesta([tool("Read"), tool("Mcp", defer_loading=True)], sid="s3"))
    # un'altra conversazione non eredita
    assert nomi(richiesta([tool("Solo")], sid="altra")) == ["Solo"]
    # senza session id: chiave = hash di system + primo messaggio utente
    sp = richiesta([tool("A")], sid="")
    sp["metadata"] = {}
    sp2 = richiesta([tool("B")], sid="", turni=2)
    sp2["metadata"] = {}
    assert nomi(sp) == ["A"] and nomi(sp2) == ["A", "B"]
    # limite di memoria
    for i in range(r.MAX_CONVERSAZIONI + 20):
        nomi(richiesta([tool("X")], sid=f"lim{i}"))
    assert len(r._tools_visti) == r.MAX_CONVERSAZIONI
    print("OK test_rotta_tools")


if __name__ == "__main__":
    main()
