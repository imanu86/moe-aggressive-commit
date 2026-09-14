"""Replay dei piani storici con la partizione CPU/GPU della fase P1.

Con `--cpu-max 0` esegue anche il **confronto passo per passo** con la politica di
riferimento (`analyze_trace.py`, classe `Cache`), che sulla stessa traccia
riproduce senza differenze i miss misurati dalla GPU: per ogni piano si
confrontano richieste uniche, numero e identita' dei miss, slot assegnati e
vittime; dopo l'ammissione differita si confrontano la mappatura expert/slot,
la frequenza, l'epoca e l'ordine di recenza degli slot.

Con `--cpu-max 1` o `2` le curve di colpi/miss/byte sono **solo informative**: il
piano dice esplicitamente che non si pretende lo stesso tasso di colpi della
vecchia ammissione, e da qui non si ricava nessun t/s.

Uso tipico:
    python replay_p1.py --trace <trace64.jsonl> --cpu-max 0 --out p1_cpu0.json
    python replay_p1.py --trace <trace64.jsonl> --cpu-max 2 --cpu-order route
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import pathlib
import sys

QUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))

from cache_cpu_gpu import (CacheCpuGpu, ORDINI_CPU, istantanea_riferimento,
                           pesi_sintetici)

RIFERIMENTO_DEFAULT = QUI.parent / "strumenti_qwen38_13settembre" / "analyze_trace.py"


def carica_riferimento(percorso: pathlib.Path):
    spec = importlib.util.spec_from_file_location("riferimento_politica", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def firma_riferimento(cache, experts, step):
    """Esegue un passo del riferimento e ne ricava la stessa firma del piano."""
    expert_for_prima = list(cache.expert_for)
    miss = [e for e in experts if e not in cache.slot_for]
    cache.replay(experts, step)
    slots = [cache.slot_for[e] for e in miss]
    vittime = [expert_for_prima[s] for s in slots]
    return (len(experts), len(miss), tuple(miss), tuple(slots), tuple(vittime))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=pathlib.Path, required=True)
    ap.add_argument("--slots", type=int, default=64)
    ap.add_argument("--experts", type=int, default=512)
    ap.add_argument("--cpu-max", type=int, default=0)
    ap.add_argument("--cpu-order", choices=ORDINI_CPU, default="route")
    ap.add_argument("--strato-escluso", type=int, action="append", default=[],
                    help="strato non idoneo al ramo CPU (per esempio il 2, IQ3_S)")
    ap.add_argument("--no-verify", action="store_true",
                    help="salta il confronto con il riferimento anche con cpu-max 0")
    ap.add_argument("--riferimento", type=pathlib.Path, default=RIFERIMENTO_DEFAULT)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--max-differenze", type=int, default=10)
    ap.add_argument("--controllo-negativo", action="store_true",
                    help="anticipa di un passo il decadimento: il confronto DEVE trovare differenze")
    args = ap.parse_args()

    verifica = args.cpu_max == 0 and not args.no_verify
    riferimento = carica_riferimento(args.riferimento) if verifica else None

    cache: dict[tuple[int, int], CacheCpuGpu] = {}
    riferimenti: dict[tuple[int, int], object] = {}
    attesa_stato: dict[tuple[int, int], dict] = {}
    incarnazione_attiva: dict[int, tuple[int, int]] = {}
    passo_atteso: dict[tuple[int, int], int] = {}

    totali = collections.Counter()
    caldi = collections.Counter()
    per_strato: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    differenze: list[dict] = []
    differenze_per_tipo: collections.Counter = collections.Counter()
    n_differenze = 0
    piani_confrontati = 0
    stati_confrontati = 0
    piani = 0
    pendenti_mai_applicati = 0
    residenti_fantasma = 0

    with open(args.trace, encoding="utf-8") as sorgente:
        for numero, linea in enumerate(sorgente, 1):
            if not linea.strip():
                continue
            rec = json.loads(linea)
            gruppo, strato, step = int(rec["group"]), int(rec["layer"]), int(rec["step"])
            k, rows = int(rec["k"]), int(rec["rows"])
            bpm = int(rec["bytes_per_miss"])
            ids = [int(x) for x in rec["ids"]]
            chiave = (gruppo, strato)
            if len(ids) != k * rows:
                raise SystemExit(f"riga {numero}: ids {len(ids)} != k*rows {k*rows}")
            atteso = passo_atteso.get(chiave, 0) + 1
            if step != atteso:
                raise SystemExit(f"riga {numero}: passo {step}, atteso {atteso}")
            passo_atteso[chiave] = step

            vecchia = incarnazione_attiva.get(strato)
            if vecchia is not None and vecchia != chiave:
                # invalidazione dell'incarnazione: il piano pendente della vecchia
                # cache non viene mai applicato, i buffer sono rilasciati.
                if cache[vecchia].pending is not None:
                    pendenti_mai_applicati += 1
                del cache[vecchia]
                riferimenti.pop(vecchia, None)
                attesa_stato.pop(vecchia, None)
            incarnazione_attiva[strato] = chiave

            if chiave not in cache:
                cache[chiave] = CacheCpuGpu(
                    n_slots=args.slots, n_experts=args.experts, cpu_max=args.cpu_max,
                    bytes_per_miss=bpm, cpu_order=args.cpu_order,
                    layer_eligible=strato not in args.strato_escluso,
                    epoch_bias=1 if args.controllo_negativo else 0)
                if verifica:
                    riferimenti[chiave] = riferimento.Cache(args.slots)
            sim = cache[chiave]
            pesi = pesi_sintetici(step, len(ids))
            piano = sim.plan(ids, k=k, rows=rows, pesi=pesi, bytes_per_miss=bpm)
            piani += 1

            # nessun residente fantasma: gli esperti serviti dalla CPU non
            # possono essere residenti in nessun momento successivo per effetto
            # di questo piano.
            esperti_cpu = {e for _, e in piano.miss_cpu}
            if esperti_cpu & sim.residenti():
                residenti_fantasma += 1

            if verifica:
                atteso_stato = attesa_stato.pop(chiave, None)
                if atteso_stato is not None:
                    stati_confrontati += 1
                    if piano.stato_dopo_commit != atteso_stato:
                        n_differenze += 1
                        differenze_per_tipo["stato"] += 1
                        if len(differenze) < args.max_differenze:
                            differenze.append({"riga": numero, "tipo": "stato",
                                               "gruppo": gruppo, "strato": strato,
                                               "passo": step})
                firma_rif = firma_riferimento(
                    riferimenti[chiave], list(dict.fromkeys(ids)), step)
                piani_confrontati += 1
                if piano.firma() != firma_rif:
                    n_differenze += 1
                    differenze_per_tipo["piano"] += 1
                    if len(differenze) < args.max_differenze:
                        differenze.append({"riga": numero, "tipo": "piano",
                                           "gruppo": gruppo, "strato": strato,
                                           "passo": step,
                                           "simulatore": list(piano.firma()),
                                           "riferimento": list(firma_rif)})
                attesa_stato[chiave] = istantanea_riferimento(riferimenti[chiave])

            voci = {
                "plans": 1,
                "unique_requests": piano.n_unique,
                "gpu_hits": piano.hits,
                "gpu_misses": piano.n_miss_gpu,
                "cpu_misses": piano.n_miss_cpu,
                "pairs_total": piano.n_routes,
                "pairs_cpu": len(piano.job_cpu),
                "bytes_loaded": piano.n_miss_gpu * bpm,
                "victims_evicted": sum(1 for v in piano.vittime if v >= 0),
            }
            totali.update(voci)
            per_strato[strato].update(voci)
            if step > 64:
                caldi.update(voci)

    # confronto dello stato finale di ogni incarnazione ancora viva: il
    # simulatore applica il piano pendente solo per la verifica.
    if verifica:
        for chiave, sim in cache.items():
            atteso_stato = attesa_stato.get(chiave)
            if atteso_stato is None:
                continue
            sim.flush_per_verifica()
            stati_confrontati += 1
            if sim.istantanea() != atteso_stato:
                n_differenze += 1
                differenze_per_tipo["stato_finale"] += 1
                if len(differenze) < args.max_differenze:
                    differenze.append({"tipo": "stato_finale", "gruppo": chiave[0],
                                       "strato": chiave[1]})

    def percentuali(c: collections.Counter) -> dict:
        uniche = c["unique_requests"]
        fuori = {k: v for k, v in c.items()}
        if uniche:
            fuori["gpu_hit_percent"] = 100.0 * c["gpu_hits"] / uniche
            fuori["gpu_miss_percent"] = 100.0 * c["gpu_misses"] / uniche
            fuori["cpu_miss_percent"] = 100.0 * c["cpu_misses"] / uniche
            fuori["somma_invariante_1"] = (
                c["gpu_hits"] + c["gpu_misses"] + c["cpu_misses"] == uniche)
        return fuori

    risultato = {
        "trace": str(args.trace),
        "trace_sha256": hashlib.sha256(args.trace.read_bytes()).hexdigest(),
        "slots": args.slots,
        "n_experts": args.experts,
        "cpu_max": args.cpu_max,
        "cpu_order": args.cpu_order,
        "strati_esclusi": sorted(args.strato_escluso),
        "piani": piani,
        "incarnazioni": len(passo_atteso),
        "verifica_cpu0": verifica,
        "controllo_negativo": args.controllo_negativo,
        "piani_confrontati": piani_confrontati,
        "stati_confrontati": stati_confrontati,
        "differenze": n_differenze,
        "differenze_per_tipo": dict(differenze_per_tipo),
        "differenze_prime": differenze,
        "residenti_fantasma": residenti_fantasma,
        "piani_pendenti_mai_applicati": pendenti_mai_applicati,
        "totali": percentuali(totali),
        "caldi_passo_oltre_64": percentuali(caldi),
        "per_strato": {str(s): percentuali(c) for s, c in sorted(per_strato.items())},
        "note": [
            "I colpi con cpu_max>0 non sono confrontabili con la vecchia ammissione: i miss CPU non vengono ammessi.",
            "I byte contano solo i miss GPU effettivamente trasferiti, tre banche per esperto.",
            "I pesi del router non sono nella traccia: sono sintetici e servono solo alla contabilita' dell'invariante 5.",
            "Nessun t/s si deduce da questo file.",
        ],
    }
    if args.out:
        args.out.write_text(json.dumps(risultato, indent=2) + "\n", encoding="utf-8")
    sintesi = {k: risultato[k] for k in (
        "piani", "verifica_cpu0", "piani_confrontati", "stati_confrontati",
        "differenze", "residenti_fantasma", "piani_pendenti_mai_applicati")}
    sintesi["caldi"] = {k: risultato["caldi_passo_oltre_64"][k] for k in (
        "unique_requests", "gpu_hits", "gpu_misses", "cpu_misses", "pairs_cpu",
        "bytes_loaded", "gpu_hit_percent", "somma_invariante_1")}
    print(json.dumps(sintesi, indent=2))
    return 1 if n_differenze or residenti_fantasma else 0


if __name__ == "__main__":
    raise SystemExit(main())
