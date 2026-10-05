"""A multi-turn chat in one engine process: the regime the user actually runs.

Turn 1 is ~12k tokens of real code (the fork's expert_source.cpp) plus a request for a long answer; every later turn
asks for another long answer (up to --gen tokens each, a different request each turn), so the context grows by
10-15k tokens per turn, up to --max-context (130k): each turn the engine reads only the new part.  The Daily's
configuration as is - whole expert arena registered, elastic cache, in-process prompt/conversation cache on - only
the operational prompt-cache file is left out.  Per turn: prompt tokens, reused prefix, prefill ms, decode t/s,
drafts, expert-cache hit rate.  Greedy (temperature 0, seed 73), Italian prompts as in the user's chats.
"""
import argparse, json, sys, threading, time
from pathlib import Path

L = Path(__file__).resolve().parent
sys.path.insert(0, str(L))
import run_keep as RK

PREFIX, CONFIG, bounded, sha = RK.PREFIX, RK.CONFIG, RK.bounded, RK.sha
SOURCE = Path(r'C:\Users\imanu\source\repos\Strata-2080Ti-core\src\core\expert_source.cpp')

TURNS = [
    "Qui sopra c'è un file C++ di un motore di inferenza per modelli mixture-of-experts. Scrivi in italiano un "
    "documento tecnico completo e molto dettagliato: per ogni funzione spiega scopo, ingressi, uscite, invarianti, "
    "casi limite e possibili bug, con frammenti di codice di esempio. Sii esaustivo e non riassumere: il documento "
    "deve essere lungo, oltre diecimila parole.",
    "Ora riscrivi in C++ moderno, completa e funzionante, la funzione expert_pool_dispatch_multi con tutte le funzioni "
    "di supporto che usa, con commenti dettagliati, e poi scrivi una suite di test unitari esaustiva (almeno trenta "
    "test, ciascuno completo). Non abbreviare nulla e non usare segnaposto.",
    "Ora scrivi un piano di ottimizzazione dettagliato di questo codice per una RTX 2080 Ti su PCIe 3 con una CPU "
    "Ryzen 7 5800X e DDR4: per ogni proposta spiega il razionale, stima il guadagno, scrivi il codice completo delle "
    "modifiche e come misurarle. Sii il più dettagliato e lungo possibile.",
    "Ora scrivi la documentazione utente completa in italiano per chi deve configurare e usare questo motore: "
    "installazione, ogni opzione con esempi, risoluzione dei problemi, domande frequenti. Molto lunga e dettagliata.",
    "Fai una revisione del codice riga per riga del file iniziale come farebbe un revisore esigente: elenca ogni "
    "problema di correttezza, concorrenza, prestazioni e leggibilità, con la correzione proposta in codice completo.",
    "Scrivi un kernel CUDA completo per sm_75 che calcoli sulla GPU il lavoro che oggi la funzione di dispatch "
    "assegna alla CPU, con il codice host che lo lancia, i controlli d'errore e una spiegazione dettagliata delle "
    "scelte di memoria condivisa e di occupazione.",
    "Scrivi un banco di prova completo in Python che misuri questo motore su conversazioni lunghe: generazione dei "
    "prompt, raccolta delle metriche, analisi statistica e grafici, con tutto il codice e la spiegazione.",
    "Scrivi una guida di migrazione dettagliata per portare questo codice da Windows a Linux: differenze di memoria "
    "pinnata, thread, I/O sui file e driver, con il codice di tutte le modifiche necessarie.",
    "Scrivi un'analisi di sicurezza e robustezza: cosa succede con file corrotti, memoria esaurita, richieste "
    "annullate o input malevoli, e per ogni caso il codice difensivo completo da aggiungere.",
    "Riassumi tutta la conversazione in un documento di progetto finale molto dettagliato, con decisioni, "
    "alternative scartate, rischi e un piano di lavoro settimana per settimana.",
]


def material(tok, target):
    """The first lines of SOURCE that make about `target` tokens."""
    lines = SOURCE.read_text(encoding='utf-8', errors='replace').splitlines()
    lo, hi = 1, len(lines)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(tok.encode('\n'.join(lines[:mid]))) <= target: lo = mid
        else: hi = mid - 1
    return '\n'.join(lines[:lo])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--build', default='build-vram1')
    ap.add_argument('--daily-exe', action='store_true', help="use the Daily config's own exe")
    ap.add_argument('--env', action='append', default=[], help='KEY=VALUE extra STRATA_ env')
    ap.add_argument('--set-opt', action='append', default=[], help='--option=value override of the Daily args')
    ap.add_argument('--drop-opt', action='append', default=[], help='--option removed from the Daily args')
    ap.add_argument('--turns', type=int, default=10)
    ap.add_argument('--max-context', type=int, default=130000, help='stop once the next prompt would pass this')
    ap.add_argument('--gen', type=int, default=14000, help='max tokens per answer')
    ap.add_argument('--first', type=int, default=12000, help='tokens of code in the first prompt')
    a = ap.parse_args()
    out = L / a.name
    assert not out.exists()
    cfg = json.loads(CONFIG.read_text())
    if a.daily_exe:
        exe = Path(cfg['exe']); pin = {'status': 'completed', 'executable_sha256': sha(exe)}
    else:
        exe = L / a.build / 'strata.exe'
        pin = json.loads((exe.parent / 'build.json').read_text())
        assert pin['status'] == 'completed' and sha(exe) == pin['executable_sha256']
    tok, template, convert, _ = PREFIX.load_helper().tokenizer_and_template(cfg)
    from serve import server
    code = material(tok, a.first)
    args = PREFIX.replace_option(list(server.engine_args(cfg)), '--prompt-cache-file', None)
    for ov in a.set_opt:
        k, v = ov.split('=', 1); assert k.startswith('--'); args = PREFIX.replace_option(args, k, v)
    for ov in a.drop_opt:
        assert ov.startswith('--') and ov in args; args = PREFIX.replace_option(args, ov, None)
    env = PREFIX.environment(cfg, out / 'unused')
    env.pop('STRATA_DUMP_FIRST_LOGITS', None)
    env.update(STRATA_DECODE_TIMING='1')
    for kv in a.env:
        k, v = kv.split('=', 1); assert k.startswith('STRATA_'); env[k] = v
    now = RK.snapshot()
    assert not now['competing'] and now['commit_free_gib'] >= 52, now
    out.mkdir()
    plan = dict(build=None if a.daily_exe else a.build, daily_exe=a.daily_exe, set_opt=a.set_opt, drop_opt=a.drop_opt,
                env_extra=a.env, args=args, turns=a.turns, gen=a.gen, first_tokens=len(tok.encode(code)), state=now,
                executable_sha256=pin['executable_sha256'], source=str(SOURCE), source_sha256=sha(SOURCE))
    (out / 'plan.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    messages = [{'role': 'system', 'content': 'Sei un ingegnere software senior. Rispondi in italiano.'}]
    result = dict(status='starting', turns=[])
    engine = server.StrataEngine(str(exe), args, cwd=cfg['cwd'], log=str(out / 'engine.log'), env=env, lazy=True)
    owned = {}
    try:
        t0 = time.monotonic()
        bounded(engine.restart, 300, engine, owned, 'Startup deadline')
        result['startup_s'] = time.monotonic() - t0
        for i in range(a.turns):
            ask = TURNS[i % len(TURNS)]
            messages.append({'role': 'user', 'content': (code + '\n\n' + ask) if i == 0 else ask})
            m, tools, kw = convert({'messages': messages, 'temperature': 0})
            ids = tok.encode(template.render(m, tools, **kw), parse_special=True)
            if len(ids) + a.gen > a.max_context:
                result['stopped'] = f'turn {i + 1}: {len(ids)} prompt tokens + {a.gen} would pass {a.max_context}'
                break
            emitted, first = [], []
            ts = time.monotonic()

            def gen():
                for token in engine.generate(ids, a.gen, dict(temperature=0, seed=73), threading.Event()):
                    if token is not None:
                        if not emitted:
                            first.append(time.monotonic())
                        emitted.append(int(token))
            bounded(gen, 2400, engine, owned, f'turn {i + 1} deadline')
            last = dict(engine.last)
            text = tok.decode(emitted)
            (out / f'turn{i + 1}.txt').write_text(text, encoding='utf-8')
            messages.append({'role': 'assistant', 'content': text})
            rec = dict(turn=i + 1, prompt_tokens=len(ids), reused=last.get('reused'), prompt_ms=last.get('prompt_ms'),
                       generated=last.get('generated'), decode_ms=last.get('decode_ms'),
                       decode_tps=last['generated'] / last['decode_ms'] * 1000 if last.get('decode_ms') else None,
                       ttft_s=first[0] - ts if first else None,
                       hit_rate=last['hits'] / last['lookups'] if last.get('lookups') else None,
                       drafts=(last.get('drafts_accepted'), last.get('drafts_offered')), finish=last.get('finish'))
            result['turns'].append(rec)
            print(json.dumps(rec), flush=True)
        result['status'] = 'completed'
    except BaseException as e:
        result.update(status='failed', error=repr(e))
        raise
    finally:
        try:
            bounded(engine.close, 35, engine, owned, 'Cleanup deadline')
        except BaseException as e:
            result['close_error'] = repr(e)
        result['cleanup_actions'] = PREFIX.terminate_owned(owned)
        (out / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
