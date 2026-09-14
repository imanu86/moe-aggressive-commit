"""Scenari dedicati del contratto P1: cambio di vittima, saturazione, riuso
ravvicinato, invalidazione delle incarnazioni, ID ai limiti, 0/1/2 job CPU,
pesi zero e non uniformi, fallback e errore di un job.

Ogni scenario controlla gli invarianti del piano e stampa un verdetto. Non
misura velocita': e' un test di stato e di contabilita'.
"""

from __future__ import annotations

import json
import pathlib
import sys

QUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))

from cache_cpu_gpu import (CacheCpuGpu, ContrattoViolato, JobCpuFallito,
                           frequenza_efficace)

BYTES = 1971200
ESITI: list[dict] = []


def registra(nome, dettaglio):
    ESITI.append({"scenario": nome, "esito": "ok", "dettaglio": dettaglio})


def atteso(condizione, messaggio):
    if not condizione:
        raise AssertionError(messaggio)


def nuova(n_slots=4, n_experts=512, cpu_max=0, **kw):
    return CacheCpuGpu(n_slots=n_slots, n_experts=n_experts, cpu_max=cpu_max,
                       bytes_per_miss=BYTES, **kw)


# --------------------------------------------------------------------------- 1
def scenario_cambio_vittima():
    """Con un miss servito dalla CPU la sequenza delle vittime cambia, perche'
    si ammette un esperto in meno e lo slot candidato resta libero piu' a lungo."""
    sequenza = [[10, 11], [12, 13], [10, 14], [15, 16]]
    vittime = {}
    residenti = {}
    for cpu_max in (0, 1):
        cache = nuova(n_slots=3, cpu_max=cpu_max)
        traccia = []
        for ids in sequenza:
            piano = cache.plan(ids, k=2, rows=1)
            traccia.append({"ids": ids, "slot": list(piano.remapped_ids),
                            "vittime": list(piano.vittime),
                            "cpu": [e for _, e in piano.miss_cpu]})
        cache.flush_per_verifica()
        vittime[cpu_max] = traccia
        residenti[cpu_max] = sorted(cache.residenti())
    atteso(vittime[0] != vittime[1], "la partizione CPU non ha cambiato nulla")
    atteso(residenti[0] != residenti[1], "residenti identici con e senza CPU")
    registra("cambio_di_vittima", {"cpu_max_0": vittime[0], "cpu_max_1": vittime[1],
                                   "residenti": residenti})


def scenario_vittima_e_argmin():
    """La vittima scelta e' l'argmin indipendente di (frequenza efficace,
    ultimo uso, indice) fra gli slot non protetti: LFU, non LRU."""
    cache = nuova(n_slots=3, cpu_max=0)
    cache.plan([1, 2, 3], k=3, rows=1)      # riempie i tre slot
    cache.plan([1, 2, 3], k=3, rows=1)      # alza la frequenza di tutti e tre
    cache.plan([1, 1, 1][:1] + [2, 3], k=3, rows=1)
    for _ in range(3):
        cache.plan([1, 2, 3], k=3, rows=1)
    cache.plan([1, 2, 9], k=3, rows=1)      # 9 e' un miss: vittima fra gli altri
    cache.flush_per_verifica()
    atteso(9 in cache.residenti(), "l'esperto ammesso non e' residente")
    atteso(3 not in cache.residenti(), "la vittima attesa era il 3")
    registra("vittima_argmin_lfu", {"residenti": sorted(cache.residenti()),
                                     "frequenze": {str(e): cache.freq[e] for e in (1, 2, 3, 9)}})


# --------------------------------------------------------------------------- 2
def scenario_saturazione():
    """Con richieste uniche pari al numero di slot ogni slot e' protetto: non
    esiste vittima legittima e il contratto rifiuta il piano. Con un miss sulla
    CPU lo stesso piano diventa eseguibile."""
    cache = nuova(n_slots=4, cpu_max=0)
    cache.plan([1, 2, 3, 4], k=4, rows=1)
    cache.plan([1, 2, 3, 4], k=4, rows=1)
    piano = cache.plan([1, 2, 3, 5], k=4, rows=1)
    atteso(piano.n_miss_gpu == 1, "atteso un solo miss")
    errore = None
    try:
        cache_piena = nuova(n_slots=4, cpu_max=0)
        cache_piena.plan([1, 2, 3, 4, 5], k=5, rows=1)
    except ContrattoViolato as exc:
        errore = str(exc)
    atteso(errore is not None, "n_routes oltre gli slot doveva essere rifiutato")
    # cache satura: quattro slot, quattro residenti, quattro miss nuovi.
    # Con cpu_max=0 si sfrattano quattro esperti, con cpu_max=2 soltanto due.
    piani = {}
    for cpu_max in (0, 2):
        cache2 = nuova(n_slots=4, cpu_max=0)
        cache2.plan([1, 2, 3, 4], k=4, rows=1)
        cache2.plan([1, 2, 3, 4], k=4, rows=1)   # applica l'ammissione differita
        atteso(sorted(cache2.residenti()) == [1, 2, 3, 4], "la cache doveva essere piena")
        cache2.cpu_max = cpu_max
        piano2 = cache2.plan([5, 6, 7, 8], k=4, rows=1)
        piani[cpu_max] = piano2
    atteso(piani[0].n_miss_gpu == 4 and piani[0].n_miss_cpu == 0, "atteso ogni miss sulla GPU")
    atteso(all(v >= 0 for v in piani[0].vittime), "alla saturazione ogni vittima e' un residente")
    atteso(piani[2].n_miss_cpu == 2 and piani[2].n_miss_gpu == 2,
           "partizione attesa 2 CPU e 2 GPU alla saturazione")
    atteso(all(v >= 0 for v in piani[2].vittime), "vittime attese fra i residenti")
    atteso(len(set(piani[2].remapped_ids)) == 2,
           "le due route CPU devono usare lo slot alias di una route GPU")
    registra("saturazione", {"errore_atteso": errore,
                              "cpu_max_0": {"vittime": list(piani[0].vittime),
                                             "slot": list(piani[0].remapped_ids)},
                              "cpu_max_2": {"cpu": [e for _, e in piani[2].miss_cpu],
                                             "slot": list(piani[2].remapped_ids),
                                             "vittime": list(piani[2].vittime)}})


# --------------------------------------------------------------------------- 3
def scenario_riuso_ravvicinato():
    """Esperto servito dalla CPU al passo t e richiesto di nuovo a t+1: deve
    essere un miss di nuovo, senza residenza fantasma."""
    cache = nuova(n_slots=4, cpu_max=1)
    piano_t = cache.plan([20, 21, 22], k=3, rows=1)
    cpu_t = [e for _, e in piano_t.miss_cpu]
    atteso(len(cpu_t) == 1, "atteso un job CPU")
    piano_t1 = cache.plan([20, 21, 22], k=3, rows=1)
    cpu_t1 = [e for _, e in piano_t1.miss_cpu]
    atteso(cpu_t[0] not in cache.residenti(),
           "l'esperto servito dalla CPU e' diventato residente: fantasma")
    atteso(cpu_t[0] in cpu_t1 or cpu_t[0] in [e for _, e, _ in piano_t1.miss_gpu],
           "l'esperto CPU doveva essere di nuovo un miss")
    # la frequenza logica include comunque la route CPU
    atteso(cache.freq[cpu_t[0]] >= 1, "invariante 3: frequenza della route CPU persa")
    registra("riuso_ravvicinato", {
        "cpu_t": cpu_t, "cpu_t1": cpu_t1,
        "miss_gpu_t1": [e for _, e, _ in piano_t1.miss_gpu],
        "frequenza_cpu": cache.freq[cpu_t[0]],
        "residenti": sorted(cache.residenti())})


# --------------------------------------------------------------------------- 4
def scenario_invalidazione_incarnazione():
    """Una nuova incarnazione dello stesso strato riparte vuota e il piano
    pendente della precedente non viene mai applicato."""
    vecchia = nuova(n_slots=4, cpu_max=1)
    vecchia.plan([30, 31, 32], k=3, rows=1)
    piano = vecchia.plan([30, 33, 34], k=3, rows=1)
    atteso(vecchia.pending is piano, "il piano dovrebbe restare pendente")
    ammessi_non_applicati = [e for _, e, _ in piano.miss_gpu]
    residenti_prima = sorted(vecchia.residenti())
    nuovainc = nuova(n_slots=4, cpu_max=1)     # unbind + bind: arrays azzerati
    piano_nuovo = nuovainc.plan([30, 33, 34], k=3, rows=1)
    atteso(piano_nuovo.hits == 0, "la nuova incarnazione non deve avere colpi")
    atteso(not nuovainc.residenti(), "la nuova incarnazione parte vuota")
    registra("invalidazione_incarnazioni", {
        "ammissione_persa": ammessi_non_applicati,
        "residenti_vecchia": residenti_prima,
        "colpi_nuova": piano_nuovo.hits})


# --------------------------------------------------------------------------- 5
def scenario_id_ai_limiti():
    """ID 0 e n_experts-1 accettati; fuori intervallo rifiutati."""
    cache = nuova(n_slots=4, n_experts=512, cpu_max=2)
    piano = cache.plan([0, 511, 1], k=3, rows=1)
    atteso(set(e for _, e in piano.miss_cpu) | set(e for _, e, _ in piano.miss_gpu) == {0, 511, 1},
           "ID ai limiti non classificati")
    errori = []
    for cattivi in ([512, 1, 2], [-1, 1, 2]):
        try:
            nuova(n_slots=4, cpu_max=1).plan(cattivi, k=3, rows=1)
            errori.append(None)
        except ContrattoViolato as exc:
            errori.append(str(exc))
    atteso(all(errori), "un ID fuori intervallo doveva essere rifiutato")
    registra("id_ai_limiti", {"accettati": [0, 511, 1], "errori": errori})


# --------------------------------------------------------------------------- 6
def scenario_zero_uno_due_job():
    """Con cpu_max in {0,1,2} il numero di esperti CPU e'
    min(cpu_max, n_miss, n_unique-1); i job contano le coppie token/esperto."""
    righe = []
    for cpu_max in (0, 1, 2):
        for ids, k, rows in (([1, 2, 3], 3, 1),          # tre miss
                             ([1, 1], 1, 2),             # un unico su due token
                             ([1, 2, 1, 2], 2, 2)):      # due token, due esperti
            cache = nuova(n_slots=8, cpu_max=cpu_max)
            piano = cache.plan(ids, k=k, rows=rows)
            n_unique = piano.n_unique
            n_miss = piano.n_miss_gpu + piano.n_miss_cpu
            atteso(piano.n_miss_cpu == max(0, min(cpu_max, n_miss, n_unique - 1)),
                   f"quota CPU sbagliata per {ids} cpu_max={cpu_max}")
            atteso(len(piano.job_cpu) == sum(
                1 for r in range(piano.n_routes)
                if piano.unique_is_cpu[piano.route_unique[r]]),
                "job CPU non allineati alle route")
            righe.append({"cpu_max": cpu_max, "ids": ids, "k": k, "rows": rows,
                          "unici": n_unique, "miss": n_miss,
                          "miss_cpu": piano.n_miss_cpu, "job_cpu": len(piano.job_cpu),
                          "coppie": piano.n_routes})
    # un solo unico con cpu_max=2: nessun job, serve una route GPU reale
    cache = nuova(n_slots=8, cpu_max=2)
    piano = cache.plan([7], k=1, rows=1)
    atteso(piano.n_miss_cpu == 0, "senza route GPU reale non si usa la CPU")
    righe.append({"cpu_max": 2, "ids": [7], "k": 1, "rows": 1, "unici": 1,
                  "miss": 1, "miss_cpu": 0, "job_cpu": 0, "coppie": 1})
    registra("zero_uno_due_job_cpu", righe)


def scenario_stesso_esperto_due_token():
    """Invariante 5: i pesi si deduplicano, il calcolo su token diversi no."""
    cache = nuova(n_slots=8, cpu_max=1)
    pesi = [0.25, 0.75, 0.5, 0.5]
    piano = cache.plan([40, 41, 40, 42], k=2, rows=2, pesi=pesi)
    atteso(piano.n_miss_cpu == 1, "atteso un esperto CPU")
    if piano.job_cpu and piano.job_cpu[0][1] == 40:
        atteso(len(piano.job_cpu) == 2, "l'esperto 40 serve due token: due job")
        atteso({j[0] for j in piano.job_cpu} == {0, 1}, "i due job sono su token distinti")
    registra("stesso_esperto_due_token", {
        "job": [list(j) for j in piano.job_cpu],
        "unici": piano.n_unique, "coppie": piano.n_routes,
        "pesi_gpu": piano.pesi_gpu})


# --------------------------------------------------------------------------- 7
def scenario_pesi():
    """Pesi zero e non uniformi: il peso GPU delle route CPU e' esattamente
    zero, i pesi GPU rimanenti sono identici bit per bit e non rinormalizzati."""
    cache = nuova(n_slots=8, cpu_max=2)
    pesi = [0.0, 0.125, 0.6875, 0.1875]
    piano = cache.plan([50, 51, 52, 53], k=4, rows=1, pesi=pesi)
    cpu_routes = [r for r in range(4) if piano.unique_is_cpu[piano.route_unique[r]]]
    for r in range(4):
        if r in cpu_routes:
            atteso(piano.pesi_gpu[r] == 0.0, "route CPU con peso GPU non nullo")
        else:
            atteso(piano.pesi_gpu[r] == pesi[r], "peso GPU rinormalizzato o alterato")
    contributi = {}
    for indice, r in enumerate(cpu_routes):
        contributi[r] = piano.job_cpu[indice][2]
    atteso(all(contributi[r] == pesi[r] for r in cpu_routes),
           "il job CPU non porta il peso originale")
    registra("pesi_zero_e_non_uniformi", {
        "pesi": pesi, "pesi_gpu": piano.pesi_gpu,
        "job": [list(j) for j in piano.job_cpu], "route_cpu": cpu_routes})


# --------------------------------------------------------------------------- 8
def scenario_fallback_non_supportato():
    """Strato non idoneo: il comportamento e' identico a cpu_max=0."""
    a = nuova(n_slots=4, cpu_max=0)
    b = nuova(n_slots=4, cpu_max=2, layer_eligible=False)
    sequenza = [[1, 2, 3], [2, 4, 5], [1, 5, 6]]
    firme = ([], [])
    for ids in sequenza:
        firme[0].append(a.plan(ids, k=3, rows=1).firma())
        firme[1].append(b.plan(ids, k=3, rows=1).firma())
    a.flush_per_verifica()
    b.flush_per_verifica()
    atteso(firme[0] == firme[1], "il fallback non e' neutro")
    atteso(sorted(a.residenti()) == sorted(b.residenti()), "residenti diversi")
    registra("fallback_non_supportato", {"firme": [list(map(str, f)) for f in firme[:1]],
                                          "residenti": sorted(a.residenti())})


# --------------------------------------------------------------------------- 9
def scenario_errore_job():
    """Invariante 7: l'errore di un job invalida la richiesta, non ammette nulla
    e non dichiara completato un trasferimento."""
    cache = nuova(n_slots=3, cpu_max=1)
    cache.plan([1, 2, 3], k=3, rows=1)
    cache.flush_per_verifica()                 # niente piano pendente
    residenti_prima = sorted(cache.residenti())
    errore = None
    try:
        # 8 va alla CPU, 9 e' un miss GPU che sfratta un residente
        cache.plan([1, 8, 9], k=3, rows=1, fallisci_job_cpu=True)
    except JobCpuFallito as exc:
        errore = str(exc)
    atteso(errore is not None, "l'errore doveva propagarsi")
    atteso(cache.pending is None, "un piano fallito non deve restare pendente")
    residenti_dopo = sorted(cache.residenti())
    atteso(9 not in residenti_dopo and 8 not in residenti_dopo,
           "un piano fallito ha ammesso un esperto")
    atteso(len(residenti_dopo) == len(residenti_prima) - 1,
           "il vecchio residente dello slot sovrascritto doveva essere rimosso")
    rifiutato = None
    try:
        cache.plan([1, 2, 3], k=3, rows=1)
    except ContrattoViolato as exc:
        rifiutato = str(exc)
    atteso(rifiutato is not None, "dopo un errore la cache non puo' essere riusata")
    cache.pulizia_dopo_errore()
    piano = cache.plan([1, 2, 3], k=3, rows=1)
    atteso(piano.hits == 0, "dopo la pulizia la cache deve essere vuota")
    registra("errore_job_cpu", {"errore": errore, "residenti_prima": residenti_prima,
                                 "residenti_dopo": residenti_dopo,
                                 "riuso_rifiutato": rifiutato,
                                 "colpi_dopo_pulizia": piano.hits})


# -------------------------------------------------------------------------- 10
def scenario_alias_pronto():
    """Lo slot alias e' quello di una route GPU reale della richiesta corrente,
    protetta dal piano e con le tre banche pronte prima del consumo."""
    cache = nuova(n_slots=6, cpu_max=2)
    cache.plan([1, 2, 3], k=3, rows=1)
    piano = cache.plan([1, 4, 5], k=3, rows=1)
    atteso(piano.alias_slot >= 0, "alias assente")
    esperti_gpu = {piano.unique_experts[i] for i in range(piano.n_unique)
                   if not piano.unique_is_cpu[i]}
    atteso(cache.expert_for_slot[piano.alias_slot] in esperti_gpu or
           piano.alias_slot in [s for _, _, s in piano.miss_gpu],
           "l'alias non appartiene a una route GPU del piano")
    atteso(cache.banche_scritte[piano.alias_slot] == 3, "alias con banche incomplete")
    atteso(cache.slot_pronto[piano.alias_slot] is not None and
           cache.slot_pronto[piano.alias_slot] <= piano.indice,
           "alias non pronto al consumo")
    for r in range(piano.n_routes):
        if piano.unique_is_cpu[piano.route_unique[r]]:
            atteso(piano.remapped_ids[r] == piano.alias_slot, "route CPU senza alias")
    registra("alias_slot_protetto", {
        "alias": piano.alias_slot, "remapped": list(piano.remapped_ids),
        "cpu": [e for _, e in piano.miss_cpu],
        "gpu": [e for _, e, _ in piano.miss_gpu]})


# -------------------------------------------------------------------------- 11
def scenario_frequenza_include_cpu():
    """Invariante 3: le route CPU partecipano a frequenza e decadimento; la
    recenza degli slot riguarda solo gli unici GPU."""
    cache = nuova(n_slots=6, cpu_max=1)
    for _ in range(4):
        cache.plan([60, 61, 62], k=3, rows=1)
    cache.flush_per_verifica()
    atteso(cache.commit_freq == 3 * 4, "gli aggiornamenti di frequenza non coprono tutti gli unici")
    atteso(cache.commit_recenza < cache.commit_freq,
           "la recenza non deve coprire gli unici CPU")
    atteso(all(cache.freq[e] >= 1 for e in (60, 61, 62)),
           "un esperto non ha frequenza")
    registra("frequenza_include_cpu", {
        "aggiornamenti_frequenza": cache.commit_freq,
        "scritture_recenza": cache.commit_recenza,
        "frequenze": {str(e): cache.freq[e] for e in (60, 61, 62)},
        "decadimento_a_32_epoche": frequenza_efficace(8, 0, 32)})


def main() -> int:
    scenari = [scenario_cambio_vittima, scenario_vittima_e_argmin,
               scenario_saturazione, scenario_riuso_ravvicinato,
               scenario_invalidazione_incarnazione, scenario_id_ai_limiti,
               scenario_zero_uno_due_job, scenario_stesso_esperto_due_token,
               scenario_pesi, scenario_fallback_non_supportato,
               scenario_errore_job, scenario_alias_pronto,
               scenario_frequenza_include_cpu]
    falliti = []
    for funzione in scenari:
        try:
            funzione()
        except Exception as exc:                      # noqa: BLE001
            falliti.append({"scenario": funzione.__name__, "esito": "FALLITO",
                            "errore": f"{type(exc).__name__}: {exc}"})
    risultato = {"scenari": len(scenari), "superati": len(scenari) - len(falliti),
                 "falliti": falliti, "dettagli": ESITI}
    (QUI / "p1_scenari.json").write_text(
        json.dumps(risultato, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"scenari": risultato["scenari"], "superati": risultato["superati"],
                      "falliti": falliti}, indent=2, ensure_ascii=False))
    return 1 if falliti else 0


if __name__ == "__main__":
    raise SystemExit(main())
