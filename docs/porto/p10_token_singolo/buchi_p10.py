"""P10 cella 2 - anatomia dei BUCHI di inattivita' della GPU e delle sincronizzazioni.

Prende una cattura nsys (sqlite) del decode e, per FORWARD:

  * trova i buchi fra la fine di un kernel e l'inizio del successivo, e per ciascuno
    dice: ultimo kernel prima, primo kernel dopo, durata, POSIZIONE nel grafo (indice
    del nodo, contato dal salto di `graphNodeId` che segna l'inizio del grafo), e
    quali chiamate CUDA dell'host cadono dentro il buco;
  * classifica le `cudaStreamSynchronize` in base alla chiamata CUDA che le precede
    immediatamente sullo stesso filo e alla loro durata: e' l'unico modo di attribuirle
    senza stack (nsys non campiona la CPU senza privilegi di amministratore).

Il confine fra un forward e il successivo si riconosce dal salto all'indietro dei
`graphNodeId`: i nodi di un replay di grafo CUDA hanno identificatori crescenti, quindi
il punto in cui l'identificatore torna indietro e' l'inizio del grafo successivo. E' un
confine piu' preciso del marcatore periodico di P9 perche' coincide con il grafo.

Uso:
    python buchi_p10.py cattura.sqlite --md-out log/x.md --json-out log/x.json
"""
import argparse
import bisect
import json
import sqlite3
from collections import defaultdict
from pathlib import Path


def carica(conn):
    ker = list(conn.execute(
        "select k.start, k.end, ss.value, k.streamId, k.graphNodeId "
        "from CUPTI_ACTIVITY_KIND_KERNEL k "
        "join StringIds ss on ss.id = k.shortName order by k.start"))
    run = list(conn.execute(
        "select r.start, r.end, s.value, r.correlationId, r.globalTid "
        "from CUPTI_ACTIVITY_KIND_RUNTIME r "
        "join StringIds s on s.id = r.nameId order by r.start"))
    try:
        mem = list(conn.execute(
            "select start, end, bytes, copyKind, streamId, correlationId "
            "from CUPTI_ACTIVITY_KIND_MEMCPY order by start"))
    except sqlite3.OperationalError:
        mem = []
    return ker, run, mem


def confini_dal_grafo(ker):
    """Indici dei kernel che aprono un grafo: dove `graphNodeId` torna indietro."""
    conf = []
    prev = None
    for i, k in enumerate(ker):
        n = k[4]
        if n is None:
            prev = None
            continue
        if prev is not None and n < prev:
            conf.append(i)
        prev = n
    return conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite")
    ap.add_argument("--soglia-us", type=float, default=100.0)
    ap.add_argument("--md-out", default=None)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--dettaglio-buco", type=int, default=0,
                    help="stampa la sequenza delle chiamate CUDA dentro il k-esimo forward")
    args = ap.parse_args()

    conn = sqlite3.connect(args.sqlite)
    ker, run, mem = carica(conn)
    if not ker:
        raise SystemExit("nessun kernel nella cattura")

    conf = confini_dal_grafo(ker)
    if len(conf) < 4:
        raise SystemExit("solo %d confini di grafo: finestra troppo corta" % len(conf))
    # si scartano il primo e l'ultimo forward (bordi della finestra)
    conf = conf[1:-1]

    # Forward PULITI: ogni tanto il backend CUDA ri-cattura il grafo (le proprieta' di un
    # nodo sono cambiate). Quel forward gira nodo per nodo con migliaia di
    # `cudaLaunchKernel`, dura molto di piu' e ha un numero di kernel diverso: va escluso,
    # altrimenti inquina ogni media. Il criterio e' il numero MODALE di kernel.
    taglie = defaultdict(int)
    for a, b in zip(conf, conf[1:]):
        taglie[b - a] += 1
    modale = max(taglie.items(), key=lambda x: x[1])[0]
    intervalli = [(a, b) for a, b in zip(conf, conf[1:]) if b - a == modale]
    n_scartati = (len(conf) - 1) - len(intervalli)
    if not intervalli:
        raise SystemExit("nessun forward pulito")
    n_fw = len(intervalli)
    i0, i1 = intervalli[0][0], intervalli[-1][1]
    parete_ms = sum(ker[b][0] - ker[a][0] for a, b in intervalli) / 1e6 / n_fw
    nodi_per_forward = modale

    # ------------------------------------------------ integrita' geometrica (P9)
    ATTESI = {"moe_grouped_plan_decode": 48, "topk_moe_cuda": 48,
              "moe_weighted_reduction_f32": 48, "gated_delta_net_cuda": 36,
              "ssm_conv_f32": 36, "flash_attn_ext_f16": 12}
    conta = defaultdict(int)
    for a, b in intervalli:
        for k in ker[a:b]:
            conta[k[2]] += 1
    integrita = {}
    valida = True
    for nome, atteso in ATTESI.items():
        visto = conta.get(nome, 0) / n_fw
        ok = abs(visto - atteso) < 0.02
        valida = valida and ok
        integrita[nome] = {"atteso": atteso, "visto": round(visto, 3), "ok": ok}

    # ------------------------------------------------ buchi fra kernel
    soglia_ns = args.soglia_us * 1000.0
    buchi = []
    tot_inatt = 0
    fasce = defaultdict(lambda: {"n": 0, "ns": 0})
    for a, b in intervalli:
        # il buco del confine appartiene al forward che comincia
        fine_max = ker[a - 1][1] if a > 0 else ker[a][1]
        for i in range(a, b):
            st = ker[i][0]
            if st > fine_max:
                d = st - fine_max
                tot_inatt += d
                fascia = (">100us" if d >= 100000 else "20-100us" if d >= 20000 else
                          "5-20us" if d >= 5000 else "2-5us" if d >= 2000 else "<2us")
                fasce[fascia]["n"] += 1
                fasce[fascia]["ns"] += d
                if d >= soglia_ns:
                    buchi.append({"inizio": fine_max, "fine": st, "ns": d,
                                  "prima": ker[i - 1][2], "dopo": ker[i][2],
                                  "nodo": i - a})
            fine_max = max(fine_max, ker[i][1])

    run_start = [r[0] for r in run]
    gruppi = defaultdict(lambda: {"n": 0, "ns": 0, "durate": [], "nodi": defaultdict(int),
                                  "api": defaultdict(lambda: {"n": 0, "ns": 0}),
                                  "mem_n": 0, "mem_byte": 0, "mem_ns": 0})
    mem_start = [m[0] for m in mem]
    for b in buchi:
        g = gruppi[(b["prima"], b["dopo"])]
        g["n"] += 1
        g["ns"] += b["ns"]
        g["durate"].append(b["ns"])
        g["nodi"][b["nodo"]] += 1
        lo = bisect.bisect_left(run_start, b["inizio"] - 40_000_000)
        hi = bisect.bisect_right(run_start, b["fine"])
        for r in run[lo:hi]:
            a, z = max(r[0], b["inizio"]), min(r[1], b["fine"])
            if z > a:
                g["api"][r[2]]["n"] += 1
                g["api"][r[2]]["ns"] += z - a
        lo = bisect.bisect_left(mem_start, b["inizio"] - 1_000_000)
        hi = bisect.bisect_right(mem_start, b["fine"])
        for m in mem[lo:hi]:
            if m[1] > b["inizio"] and m[0] < b["fine"]:
                g["mem_n"] += 1
                g["mem_byte"] += m[2]
                g["mem_ns"] += m[1] - m[0]

    # una finestra per forward pulito: [fine dell'ultimo kernel del forward precedente,
    # inizio dell'ultimo kernel di questo forward). Cosi' il confine (dove sta tutto il
    # lavoro dell'host) appartiene al forward che comincia, e i forward sporchi restano fuori.
    finestre = [(ker[a - 1][1] if a > 0 else ker[a][0], ker[b][0]) for a, b in intervalli]
    fin_inizio = [f[0] for f in finestre]

    def dentro(t):
        j = bisect.bisect_right(fin_inizio, t) - 1
        return j >= 0 and t < finestre[j][1]

    # ------------------------------------------------ chiamate host per forward
    api_tot = defaultdict(lambda: {"n": 0, "ns": 0})
    for r in run:
        if dentro(r[0]):
            api_tot[r[2]]["n"] += 1
            api_tot[r[2]]["ns"] += r[1] - r[0]

    # ------------------------------------------------ classifica delle sync
    # Senza stack l'attribuzione si fa dal contesto: la chiamata CUDA che precede
    # immediatamente la sync sullo stesso filo, e la durata.
    #   * sync subito dopo una `cudaMemcpyAsync`  -> coda BLOCCANTE di una copia
    #     (`ggml_backend_cuda_buffer_set_tensor`, `ggml-cuda.cu:2215`)
    #   * sync subito dopo un'altra sync           -> `ggml_backend_synchronize` dello
    #     scheduler prima di un ingresso (`ggml-backend.cpp`, compute_splits)
    #   * sync lunga (> 1 ms)                      -> l'attesa del forward
    #     (`llama_context::synchronize` -> `ggml_backend_sched_synchronize`)
    per_filo = defaultdict(list)
    for r in run:
        per_filo[r[4]].append(r)
    indici = {t: [x[0] for x in v] for t, v in per_filo.items()}

    classi = defaultdict(lambda: {"n": 0, "ns": 0})
    n_sync = 0
    for r in run:
        if r[2] != "cudaStreamSynchronize_v3020" or not dentro(r[0]):
            continue
        n_sync += 1
        dur = r[1] - r[0]
        lst = per_filo[r[4]]
        j = bisect.bisect_left(indici[r[4]], r[0]) - 1
        prec = lst[j][2] if j >= 0 else "?"
        if dur > 1_000_000:
            k = "attesa del forward (> 1 ms)"
        elif prec == "cudaMemcpyAsync_v3020":
            k = "coda bloccante di una copia (dopo cudaMemcpyAsync)"
        elif prec == "cudaStreamSynchronize_v3020":
            k = "svuotamento della coda prima di un ingresso (dopo un'altra sync)"
        else:
            k = "altra (dopo %s)" % prec
        classi[k]["n"] += 1
        classi[k]["ns"] += dur

    h2d = [m for m in mem if dentro(m[0]) and m[3] == 1]
    d2h = [m for m in mem if dentro(m[0]) and m[3] == 2]
    ist = defaultdict(int)
    for m in h2d:
        ist[m[2]] += 1
    per_stream = defaultdict(lambda: {"n": 0, "byte": 0})
    for m in h2d:
        per_stream[m[4]]["n"] += 1
        per_stream[m[4]]["byte"] += m[2]

    out = {
        "file": args.sqlite,
        "n_forward_puliti": n_fw,
        "n_forward_scartati_ricattura": n_scartati,
        "nodi_gpu_per_forward": round(nodi_per_forward, 1),
        "integrita": {"valida": valida, "conteggi": integrita},
        "parete_ms_per_forward": round(parete_ms, 3),
        "gpu_inattiva_ms_per_forward": round(tot_inatt / 1e6 / n_fw, 3),
        "fasce_dei_buchi": {k: {"n_per_forward": round(v["n"] / n_fw, 2),
                                "ms_per_forward": round(v["ns"] / 1e6 / n_fw, 3)}
                            for k, v in sorted(fasce.items(), key=lambda x: -x[1]["ns"])},
        "buchi_grandi": [
            {"prima": k[0], "dopo": k[1],
             "n_per_forward": round(v["n"] / n_fw, 2),
             "ms_per_forward": round(v["ns"] / 1e6 / n_fw, 3),
             "mediana_ms": round(sorted(v["durate"])[len(v["durate"]) // 2] / 1e6, 3),
             "min_ms": round(min(v["durate"]) / 1e6, 3),
             "max_ms": round(max(v["durate"]) / 1e6, 3),
             "nodo_nel_grafo": sorted(v["nodi"].items(), key=lambda x: -x[1])[:3],
             "copie_dentro": {"n_per_buco": round(v["mem_n"] / v["n"], 2),
                              "mib_per_buco": round(v["mem_byte"] / v["n"] / (1 << 20), 3),
                              "ms_per_buco": round(v["mem_ns"] / 1e6 / v["n"], 3)},
             "api_dentro": sorted([{"api": a, "n_per_buco": round(d["n"] / v["n"], 2),
                                    "ms_per_buco": round(d["ns"] / 1e6 / v["n"], 3)}
                                   for a, d in v["api"].items()], key=lambda x: -x["ms_per_buco"])[:8]}
            for k, v in sorted(gruppi.items(), key=lambda x: -x[1]["ns"])],
        "api_host_per_forward": sorted(
            [{"api": k, "n": round(v["n"] / n_fw, 2), "ms": round(v["ns"] / 1e6 / n_fw, 3)}
             for k, v in api_tot.items()], key=lambda x: -x["n"]),
        "stream_synchronize": {
            "n_per_forward": round(n_sync / n_fw, 2),
            "classi": {k: {"n_per_forward": round(v["n"] / n_fw, 2),
                           "ms_per_forward": round(v["ns"] / 1e6 / n_fw, 3)}
                       for k, v in sorted(classi.items(), key=lambda x: -x[1]["n"])},
        },
        "copie": {
            "h2d_n": round(len(h2d) / n_fw, 2),
            "h2d_mib": round(sum(m[2] for m in h2d) / n_fw / (1 << 20), 3),
            "h2d_ms": round(sum(m[1] - m[0] for m in h2d) / 1e6 / n_fw, 3),
            "h2d_per_stream": {str(k): {"n": round(v["n"] / n_fw, 2),
                                        "mib": round(v["byte"] / n_fw / (1 << 20), 3)}
                               for k, v in per_stream.items()},
            "d2h_n": round(len(d2h) / n_fw, 2),
            "d2h_mib": round(sum(m[2] for m in d2h) / n_fw / (1 << 20), 4),
            "istogramma_h2d_byte": {str(k): round(v / n_fw, 2)
                                    for k, v in sorted(ist.items(), key=lambda x: -x[0])[:12]},
        },
    }

    r = []
    r.append("# Buchi e sincronizzazioni — %s" % Path(args.sqlite).name)
    r.append("")
    r.append("Integrita' geometrica: **%s** (%s)." % (
        "PASSATA" if valida else "FALLITA",
        ", ".join("%s %s/%s" % (k, v["visto"], v["atteso"]) for k, v in integrita.items())))
    r.append("")
    r.append("%d forward PULITI (confine = salto di `graphNodeId`, %d kernel ciascuno); "
             "%d forward scartati perche' il backend ha ri-catturato il grafo e li ha eseguiti "
             "nodo per nodo. Parete **%.3f ms**/forward, GPU inattiva **%.3f ms**/forward." % (
                 n_fw, nodi_per_forward, n_scartati, parete_ms, out["gpu_inattiva_ms_per_forward"]))
    r.append("")
    r.append("| fascia | buchi/forward | ms/forward |")
    r.append("|---|---:|---:|")
    for k, v in out["fasce_dei_buchi"].items():
        r.append("| %s | %.2f | %.3f |" % (k, v["n_per_forward"], v["ms_per_forward"]))
    r.append("")
    r.append("## Buchi oltre %.0f us" % args.soglia_us)
    for b in out["buchi_grandi"]:
        r.append("")
        r.append("### `%s` -> `%s` — %.2f/forward, %.3f ms/forward (mediana %.3f, min %.3f, max %.3f)"
                 % (b["prima"], b["dopo"], b["n_per_forward"], b["ms_per_forward"],
                    b["mediana_ms"], b["min_ms"], b["max_ms"]))
        r.append("")
        r.append("posizione nel grafo (indice del kernel dall'inizio del grafo): %s" % ", ".join(
            "%s x%d" % (n, c) for n, c in b["nodo_nel_grafo"]))
        r.append("")
        r.append("copie dentro il buco: %.2f, %.3f MiB, %.3f ms" % (
            b["copie_dentro"]["n_per_buco"], b["copie_dentro"]["mib_per_buco"],
            b["copie_dentro"]["ms_per_buco"]))
        r.append("")
        r.append("| chiamata CUDA dentro il buco | per buco | ms per buco |")
        r.append("|---|---:|---:|")
        for a in b["api_dentro"]:
            r.append("| `%s` | %.2f | %.3f |" % (a["api"], a["n_per_buco"], a["ms_per_buco"]))
    r.append("")
    r.append("## Chiamate dell'host per forward")
    r.append("")
    r.append("| chiamata | per forward | ms per forward |")
    r.append("|---|---:|---:|")
    for a in out["api_host_per_forward"]:
        r.append("| `%s` | %.2f | %.3f |" % (a["api"], a["n"], a["ms"]))
    r.append("")
    r.append("## `cudaStreamSynchronize`: %.2f per forward" % out["stream_synchronize"]["n_per_forward"])
    r.append("")
    r.append("| classe (dalla chiamata precedente sullo stesso filo) | per forward | ms |")
    r.append("|---|---:|---:|")
    for k, v in out["stream_synchronize"]["classi"].items():
        r.append("| %s | %.2f | %.3f |" % (k, v["n_per_forward"], v["ms_per_forward"]))
    r.append("")
    r.append("## Copie")
    r.append("")
    r.append("H2D %.2f copie, %.3f MiB, %.3f ms — D2H %.2f copie, %.4f MiB per forward." % (
        out["copie"]["h2d_n"], out["copie"]["h2d_mib"], out["copie"]["h2d_ms"],
        out["copie"]["d2h_n"], out["copie"]["d2h_mib"]))
    r.append("")
    r.append("| stream delle H2D | copie/forward | MiB/forward |")
    r.append("|---|---:|---:|")
    for k, v in out["copie"]["h2d_per_stream"].items():
        r.append("| %s | %.2f | %.3f |" % (k, v["n"], v["mib"]))
    r.append("")
    r.append("| byte per copia H2D | copie/forward |")
    r.append("|---|---:|")
    for k, v in out["copie"]["istogramma_h2d_byte"].items():
        r.append("| %s | %.2f |" % (k, v))
    testo = "\n".join(r) + "\n"

    if args.dettaglio_buco:
        n = args.dettaglio_buco
        a, b = conf[n], conf[n + 1]
        A, B = ker[a - 1][1], ker[a][0]
        print("--- dettaglio del confine prima del forward %d: buco %.3f ms" % (n, (B - A) / 1e6))
        print("    ultimo kernel del grafo precedente: %s (%.1f us)" % (
            ker[a - 1][2], (ker[a - 1][1] - ker[a - 1][0]) / 1e3))
        for x in run:
            if x[1] > A and x[0] < B:
                print("    %9.1f us  %-32s dur %9.2f us" % ((x[0] - A) / 1e3, x[2], (x[1] - x[0]) / 1e3))

    if args.md_out:
        Path(args.md_out).write_text(testo, encoding="utf-8")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(testo)


if __name__ == "__main__":
    main()
