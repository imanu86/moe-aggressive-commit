# cc1 (6/10 mattina): primi due casi via Claude Code (sotto-agenti Haiku -> gateway -> Strata 8100)

NON VALIDI come misura di qualita': i repo dei casi erano worktree del clone completo e `git log --all` mostrava i
commit futuri, compresa la correzione ufficiale. Su sympy-13615 l'agente lo ha detto da solo ("identica byte per byte
al fix upstream", commit 5f35c25443). Da qui i repo dei casi sono autonomi con un solo commit (tag swe-base).
Restano validi i numeri del motore (prefill, riuso, t/s): django 27 richieste, 98,5% riusato, 45,4 t/s; sympy 31
richieste, 97,7% riusato, 44,9 t/s; primo prompt di Claude Code ~39,7k token.
