"""Elastic cache with --batch 2 --batch-mtp: two concurrent long answers while another process takes VRAM and gives it
back (a desktop program that comes and goes).  The engine must shrink between batch windows, keep both answers going,
and grow again once the VRAM is free.

    python prova_elastica_batch.py --exe <strata.exe> --source <serve folder> [--hog-gib 3] [--name NOME]

Outputs are data; never execute model text.
"""
import argparse, ctypes, json, re, threading, time

import agente as A

CUDART = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\cudart64_12.dll'
Q = ["Scrivi un saggio lungo e dettagliato sulla storia dei calcolatori, dagli abachi ai processori moderni.",
     "Spiega in modo lungo e dettagliato come funziona un compilatore, fase per fase, con esempi."]


def hog(gib, hold_s, events):
    rt = ctypes.WinDLL(CUDART)
    ptrs = []
    for _ in range(int(gib * 4)):   # 256 MiB blocks: as much as fits up to gib
        p = ctypes.c_void_p()
        if rt.cudaMalloc(ctypes.byref(p), ctypes.c_size_t(256 << 20)) != 0:
            break
        ptrs.append(p)
    events.append((time.monotonic(), f'hog presi {len(ptrs) * 256} MiB'))
    time.sleep(hold_s)
    for p in ptrs:
        rt.cudaFree(p)
    events.append((time.monotonic(), 'hog liberati'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--source', required=True)
    ap.add_argument('--hog-gib', type=float, default=3)
    ap.add_argument('--name', default='elastica_batch')
    a = ap.parse_args()
    out = A.P.DATA / 'runs_cc' / a.name
    out.mkdir(parents=True, exist_ok=True)
    import os
    os.environ['STRATA_ELASTIC_TRACE'] = '1'
    res, events = {}, []
    with A.Server(out, exe=a.exe, source=a.source, extra=('--batch', '2', '--batch-mtp')) as srv:
        t0 = time.monotonic()

        def one(i):
            s = time.monotonic()
            try:
                r = A.get('/v1/chat/completions', dict(model=srv.model, temperature=0, max_tokens=1500,
                                                       messages=[dict(role='user', content=Q[i])],
                                                       chat_template_kwargs=dict(enable_thinking=False)), timeout=1800)
                res[i] = dict(ok=True, s=round(time.monotonic() - s, 1), tokens=r['usage']['completion_tokens'])
            except Exception as e:   # noqa: BLE001
                res[i] = dict(ok=False, s=round(time.monotonic() - s, 1), err=repr(e)[:300])

        th = [threading.Thread(target=one, args=(i,)) for i in range(2)]
        for t in th:
            t.start()
        time.sleep(15)   # both slots decoding
        h = threading.Thread(target=hog, args=(a.hog_gib, 25, events))
        h.start()
        for t in th + [h]:
            t.join()
        time.sleep(20)   # room again: the cache grows back
        log = (out / 'engine.log').read_text(encoding='utf-8', errors='replace').splitlines()
    el = [l for l in log if l.startswith('strata elastic:') or 'elastic is' in l or 'stopped' in l]
    rep = dict(answers=res, events=[(round(t - t0, 1), e) for t, e in events], elastic=el[-30:],
               batch=[l[:200] for l in log if l.startswith('strata batch: ') and 'windows' in l][-6:])
    (out / 'esito.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
