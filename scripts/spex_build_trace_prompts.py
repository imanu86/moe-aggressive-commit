"""Track SPEX — costruisce i 3 prompt-set per la sessione trace su pod (H200).

Set:
  generale_ita/  12 prompt di prosa italiana, argomenti diversi (n_decode 400)
  coding_en/     12 prompt di coding in inglese (n_decode 400)
  dominio_kb/     8 prompt di CONSTRUCT REALI con blocco FAMILY_KB iniettato = workload
                  low-confidence della pipeline Segnali (n_decode 250)

Fedeltà al runner (local_runner_v2.py):
  - blocco KB: build_family_kb_block reimplementata IDENTICA (:491-523, max 60 esempi,
    char_budget 16000) dalle family kb_v2/family_<TECH>.json
  - assemblaggio recall verbatim (:1747): fam_block + "\n\n=== PROMO DA ESTRARRE ===\n" + base_user
  - APPROSSIMAZIONE dichiarata: la CLI ds4 prende un solo -p → system e user concatenati
    (system + "\n\n" + recall_user). La forma del workload (16k char KB + promo) è preservata.
  - KB usata: FAMILY statica (fallback ufficiale del runner). Il retrieval promo_recall produce
    blocchi della stessa forma/lunghezza → per il ROUTING il workload è equivalente. Dichiarato.

Indici raft DISGIUNTI dal track REAP (loro: stratificati 0,9,18,...,135 + 7,45,91,133).
I testi di dominio_kb restano GITIGNORED (KB protetta); manifest con sha256 committato.
"""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, 'runs', 'spex', '2026-07-05_trace_prompts')
RAFT = r'C:\Users\imanu\source\repos\bonus-kb\bonusx-kb\retrieval\ft\raft_eval.jsonl'
KB_V2 = r'C:\Users\imanu\llama\pipeline\kb_v2'
REAP_USED = set(range(0, 152, 9)) | {7, 45, 91, 133}          # copertura prudente degli indici REAP
KB_CANDIDATES = [3, 22, 40, 58, 76, 94, 112, 130, 5, 24, 42, 60, 78, 96, 114, 132]

GENERALE_ITA = [
    ("storia", "Racconta in modo discorsivo le cause principali della caduta dell'Impero Romano d'Occidente, con esempi concreti."),
    ("cucina", "Spiega passo passo come preparare una vera carbonara romana, con gli errori tipici da evitare."),
    ("viaggi", "Descrivi un itinerario di dieci giorni in Giappone per un primo viaggio, tra citta' e campagna."),
    ("sport", "Spiega come impostare un piano di allenamento per passare da zero a correre dieci chilometri in tre mesi."),
    ("finanza", "Spiega a una persona giovane come funziona un mutuo prima casa in Italia e a cosa stare attenti."),
    ("giardino", "Guida pratica alla coltivazione dei pomodori sul balcone, dalla semina alla raccolta."),
    ("salute", "Spiega in modo semplice come funziona il sistema immunitario umano e perche' i vaccini lo aiutano."),
    ("auto", "Analizza pro e contro delle auto elettriche oggi in Italia per chi fa molti chilometri."),
    ("filosofia", "Introduci la filosofia stoica e spiega come applicarla ai problemi quotidiani moderni."),
    ("fotografia", "Spiega le basi della fotografia notturna: impostazioni, attrezzatura e composizione."),
    ("vino", "Racconta cosa rende speciale il Barolo: territorio, vitigno, invecchiamento e abbinamenti."),
    ("educazione", "Discuti come gestire il tempo davanti agli schermi per i bambini, con consigli pratici per i genitori."),
]

CODING_EN = [
    ("python-csv", "Write a Python function that reads a CSV file, removes duplicate rows based on a key column, and writes the result back. Include error handling and a docstring."),
    ("js-debounce", "Explain what debouncing is in JavaScript and implement a debounce utility with leading and trailing options."),
    ("sql-window", "Explain SQL window functions with practical examples: running totals, rank within groups, and moving averages."),
    ("c-pointers", "Explain the most common pointer mistakes in C with small code examples and how to fix each one."),
    ("py-asyncio", "Write an async Python scraper that fetches a list of URLs concurrently with a semaphore limit and timeout handling."),
    ("regex-email", "Discuss why validating emails with regex is tricky, show a reasonable pattern, and explain its limitations."),
    ("git-rebase", "Explain git rebase vs merge with concrete scenarios, and show how to safely rewrite local history."),
    ("docker-multi", "Write a multi-stage Dockerfile for a Node.js app and explain each stage and the size benefits."),
    ("rust-owner", "Introduce Rust ownership and borrowing for a C++ developer, with small examples that fail to compile and why."),
    ("api-paging", "Design cursor-based pagination for a REST API: endpoint shape, cursor encoding, and edge cases."),
    ("test-mock", "Explain mocking in unit tests with Python examples: when to mock, when not to, and common pitfalls."),
    ("refactor", "Review this function and refactor it: def f(l):\n  r=[]\n  for i in range(len(l)):\n    if l[i] not in r: r.append(l[i])\n  return r\nExplain complexity and provide a better version."),
]


def sha(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()


def load_family(tech):
    p = os.path.join(KB_V2, f'family_{tech}.json')
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def build_family_kb_block(technique, max_examples=60, char_budget=16000):
    """Reimplementazione IDENTICA a local_runner_v2.build_family_kb_block (:491-523)."""
    fam = load_family(technique)
    if not fam:
        return ''
    examples = fam.get('all_examples') or fam.get('few_shot') or []
    if isinstance(examples, list) and len(examples) > max_examples:
        examples = examples[:max_examples]
    parts = [f"=== FAMILY_KB tecnica {technique} (riferimento per analogia) ==="]
    if fam.get('definition'):
        parts.append("DEFINIZIONE:\n" + str(fam['definition']))
    rf = fam.get('required_fields')
    if rf:
        parts.append("CAMPI RICHIESTI: " + ', '.join(str(x) for x in rf))
    if examples:
        parts.append("ESEMPI REALI DELLA FAMIGLIA (JSON, uno per riga):")
        used = 0
        for ex in examples:
            try:
                line = json.dumps(ex, ensure_ascii=False)
            except Exception:
                continue
            if used + len(line) > char_budget:
                break
            parts.append(line)
            used += len(line)
    parts.append("ISTRUZIONE: ragiona sulla FAMIGLIA qui sopra, conferma la technique e completa per "
                 "analogia i campi mancanti o dubbi della PROMO. Mantieni lo stesso schema JSON di output.")
    return "\n\n".join(parts)


def main():
    rows = [json.loads(l) for l in open(RAFT, encoding='utf-8')]
    manifest = {
        'source_raft': RAFT.replace('\\', '/'),
        'source_sha256': sha(open(RAFT, encoding='utf-8').read()),
        'kb_block': 'family_statica (build_family_kb_block reimpl. fedele; retrieval promo_recall produce blocchi di forma equivalente — dichiarato)',
        'cli_note': 'ds4 CLI single-prompt: system+user concatenati; forma workload preservata',
        'prompts': [],
    }
    sets = []
    for i, (tag, txt) in enumerate(GENERALE_ITA):
        sets.append(('generale_ita', f'g{i:02d}_{tag}.txt', 'prosa_ita', txt, 400, None))
    for i, (tag, txt) in enumerate(CODING_EN):
        sets.append(('coding_en', f'c{i:02d}_{tag}.txt', 'coding_en', txt, 400, None))

    picked = 0
    for idx in KB_CANDIDATES:
        if picked >= 8:
            break
        if idx in REAP_USED or idx >= len(rows):
            continue
        m = rows[idx]['messages']
        system, user, gold = m[0]['content'], m[1]['content'], m[2]['content']
        t = re.search(r'"technique"\s*:\s*"([^"]+)"', gold)
        if not t:
            continue
        tech = t.group(1)
        fam = build_family_kb_block(tech)
        if not fam:
            continue
        recall_user = fam + "\n\n=== PROMO DA ESTRARRE ===\n" + user
        full = system + "\n\n" + recall_user
        sets.append(('dominio_kb', f'k{picked:02d}_idx{idx}_{tech}.txt', 'construct_kb_recall', full, 250,
                     {'raft_index': idx, 'technique': tech, 'fam_chars': len(fam)}))
        picked += 1

    for d in ('generale_ita', 'coding_en', 'dominio_kb'):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    for setname, fname, kind, text, ntok, extra in sets:
        p = os.path.join(OUT, setname, fname)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(text)
        entry = {'set': setname, 'file': fname, 'kind': kind, 'chars': len(text),
                 'sha256': sha(text), 'n_decode_target': ntok}
        if extra:
            entry.update(extra)
        manifest['prompts'].append(entry)

    with open(os.path.join(OUT, 'prompts_manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, '.gitignore'), 'w') as f:
        f.write('dominio_kb/*.txt\n')  # KB protetta; ita/coding sono testo nostro e restano
    n_kb = sum(1 for s in sets if s[0] == 'dominio_kb')
    print(f"OK: {len(sets)} prompt ({n_kb} kb). Manifest: {os.path.join(OUT, 'prompts_manifest.json')}")


if __name__ == '__main__':
    main()
