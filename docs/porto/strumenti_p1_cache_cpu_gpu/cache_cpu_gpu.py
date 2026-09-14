"""Simulatore della cache esperti con partizione dei miss fra CPU e GPU (fase P1).

Riferimento della politica attuale: `analyze_trace.py` (classe `Cache`), che sulla
traccia storica di 36.913 piani riproduce senza differenze i miss misurati dalla
GPU. Qui la stessa politica viene riscritta con l'**ammissione differita
esplicita** del kernel reale (`fork-moe-kernels.cuh`, `moe_grouped_plan_decode`:
il commit del piano precedente avviene all'inizio della chiamata successiva) e
con la partizione dei miss in CPU/GPU **prima** dell'assegnazione degli slot.

Nessuna misura di velocita' viene prodotta o dedotta da questo file: conta
richieste uniche, colpi, miss, coppie token/esperto e byte dei soli miss GPU.

Convenzioni prese dal codice reale:
  - epoca della frequenza: `passo >> 6` con passo a base zero, quindi
    `(step - 1) >> 6` sui passi della traccia (che sono a base uno);
  - frequenza efficace: `freq >> epoche_trascorse`, azzerata oltre 32 epoche;
  - vittima: minimo di (frequenza efficace, ultimo uso, indice di slot) fra gli
    slot non protetti dal piano corrente;
  - orologio: il dispositivo riserva `n_routes` tick per piano e assegna
    `clock_begin + indice_unico + 1` allo slot dell'unico; contano solo gli
    ordini relativi, non i valori assoluti.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib


class ContrattoViolato(AssertionError):
    """Un invariante del contratto P1 non e' rispettato."""


class JobCpuFallito(RuntimeError):
    """Invariante 7: l'errore di un job invalida la richiesta."""


def frequenza_efficace(freq: int, epoca_memorizzata: int, epoca: int) -> int:
    if epoca_memorizzata > epoca:
        raise ContrattoViolato("epoca memorizzata nel futuro")
    trascorse = epoca - epoca_memorizzata
    return freq >> trascorse if trascorse < 32 else 0


ORDINI_CPU = ("route", "expert", "freq", "freq_high", "last")


class Piano:
    """Risultato di una chiamata al planner, con i tre insiemi separati."""

    __slots__ = ("indice", "step", "epoca", "k", "rows", "n_routes", "ids",
                 "pesi", "unique_experts", "route_unique", "unique_slots",
                 "unique_is_cpu", "hits", "miss_gpu", "miss_cpu", "vittime",
                 "remapped_ids", "pesi_gpu", "job_cpu", "alias_slot",
                 "bytes_per_miss", "clock_begin", "stato_dopo_commit")

    def __init__(self, **campi):
        for nome in self.__slots__:
            setattr(self, nome, campi.get(nome))

    @property
    def n_unique(self) -> int:
        return len(self.unique_experts)

    @property
    def n_miss_gpu(self) -> int:
        return len(self.miss_gpu)

    @property
    def n_miss_cpu(self) -> int:
        return len(self.miss_cpu)

    def firma(self) -> tuple:
        """Contenuto confrontabile passo per passo con il riferimento: gli ID dei
        miss in ordine di indice unico, gli slot assegnati e le vittime."""
        miss = sorted([(i, e) for i, e in self.miss_cpu] +
                      [(i, e) for i, e, _ in self.miss_gpu])
        return (self.n_unique, len(miss), tuple(e for _, e in miss),
                tuple(s for _, _, s in self.miss_gpu), tuple(self.vittime))


class CacheCpuGpu:
    """Una incarnazione di cache: un gruppo legato, uno strato fisico."""

    def __init__(self, n_slots: int, n_experts: int = 512, cpu_max: int = 0,
                 frequency_aware: bool = True, bytes_per_miss: int = 0,
                 layer_eligible: bool = True, cpu_order: str = "route",
                 epoch_bias: int = 0):
        if n_slots < 1 or n_experts < 1:
            raise ValueError("n_slots e n_experts devono essere positivi")
        if cpu_max < 0:
            raise ValueError("cpu_max non puo' essere negativo")
        if cpu_order not in ORDINI_CPU:
            raise ValueError(f"ordine CPU sconosciuto: {cpu_order}")
        self.n_slots = n_slots
        self.n_experts = n_experts
        self.cpu_max = cpu_max
        self.frequency_aware = frequency_aware
        self.bytes_per_miss = bytes_per_miss
        self.layer_eligible = layer_eligible
        self.cpu_order = cpu_order
        # `epoch_bias` serve solo al controllo negativo: sposta l'epoca di uno,
        # cioe' riproduce il vecchio difetto del simulatore (decadimento
        # anticipato di un passo). Con 0 la semantica e' quella del kernel.
        self.epoch_bias = epoch_bias
        # stato del dispositivo
        self.slot_for_expert: dict[int, int] = {}
        self.expert_for_slot = [-1] * n_slots
        self.last_used = [0] * n_slots
        self.freq: dict[int, int] = collections.defaultdict(int)
        self.epoch_of: dict[int, int] = collections.defaultdict(int)
        self.clock_riservato = 0
        self.step_dispositivo = 0
        # residenza a tre banche e generazione di prontezza
        self.banche_scritte = [0] * n_slots
        self.slot_pronto: list[int | None] = [None] * n_slots
        # fase differita
        self.pending: Piano | None = None
        self.n_piani = 0
        self.contaminato = False
        # contatori
        self.contatori = collections.Counter()
        self.commit_freq = 0
        self.commit_recenza = 0

    # ------------------------------------------------------------------ commit
    def _commit(self) -> None:
        """Applica il piano precedente: e' il punto in cui un trasferimento
        completato diventa residente (fork-moe-kernels.cuh, ramo
        `plan->status == MOE_GROUPED_PLAN_READY`)."""
        piano = self.pending
        self.pending = None
        if piano is None:
            return
        for _, expert, slot in piano.miss_gpu:
            if not (0 <= expert < self.n_experts) or not (0 <= slot < self.n_slots):
                raise ContrattoViolato("ammissione con esperto o slot fuori intervallo")
            if self.banche_scritte[slot] != 3:
                raise ContrattoViolato("invariante 4: banche incomplete al commit")
            vecchio = self.expert_for_slot[slot]
            if vecchio >= 0:
                del self.slot_for_expert[vecchio]
            self.expert_for_slot[slot] = expert
            self.slot_for_expert[expert] = slot
        for indice, expert in enumerate(piano.unique_experts):
            if piano.unique_is_cpu[indice]:
                # invariante 3: la recenza degli slot riguarda solo slot validi;
                # il tick di orologio viene consumato ma non scritto.
                pass
            else:
                slot = piano.unique_slots[indice]
                if slot < 0:
                    raise ContrattoViolato("unico GPU senza slot al commit")
                self.last_used[slot] = piano.clock_begin + indice + 1
                self.commit_recenza += 1
            # invariante 3: tutte le richieste logiche, anche quelle CPU,
            # partecipano a frequenza e decadimento.
            self.freq[expert] = frequenza_efficace(
                self.freq[expert], self.epoch_of[expert], piano.epoca) + 1
            self.epoch_of[expert] = piano.epoca
            self.commit_freq += 1
        # invariante 2: nessun residente fantasma. Un esperto servito dalla CPU
        # non e' stato trasferito e non puo' risultare residente per effetto di
        # questo commit.
        for _, expert in piano.miss_cpu:
            if self.slot_for_expert.get(expert, -1) != -1:
                self.contatori["residenti_fantasma"] += 1
                raise ContrattoViolato("invariante 2: residente fantasma dopo il commit")
        self._controlla_mappatura()

    def flush_per_verifica(self) -> None:
        """Applica un eventuale piano pendente. Nel motore reale l'ultima
        ammissione di una incarnazione non viene mai applicata: qui serve solo a
        confrontare lo stato con il riferimento a ammissione immediata."""
        self._commit()

    # -------------------------------------------------------------- invarianti
    def _controlla_mappatura(self) -> None:
        for slot, expert in enumerate(self.expert_for_slot):
            if expert < 0:
                continue
            if self.slot_for_expert.get(expert, -1) != slot:
                raise ContrattoViolato("invariante 4: mappatura expert/slot non reciproca")
            if self.last_used[slot] == 0:
                raise ContrattoViolato("invariante 4: residente senza recenza")
            if self.banche_scritte[slot] != 3:
                raise ContrattoViolato("invariante 4: residente con banche incomplete")
        for expert, slot in self.slot_for_expert.items():
            if not (0 <= slot < self.n_slots) or self.expert_for_slot[slot] != expert:
                raise ContrattoViolato("invariante 4: slot_for_expert incoerente")

    def residenti(self) -> set[int]:
        return set(self.slot_for_expert)

    def pulizia_dopo_errore(self) -> None:
        """Equivalente della coppia unbind/bind: l'incarnazione viene buttata e
        ricreata vuota. E' l'unico modo di riprendere dopo un errore in volo."""
        self.slot_for_expert.clear()
        self.expert_for_slot = [-1] * self.n_slots
        self.last_used = [0] * self.n_slots
        self.freq.clear()
        self.epoch_of.clear()
        self.banche_scritte = [0] * self.n_slots
        self.slot_pronto = [None] * self.n_slots
        self.pending = None
        self.contaminato = False

    # -------------------------------------------------------------- pianifica
    def plan(self, ids, k: int, rows: int, pesi=None, bytes_per_miss=None,
             fallisci_job_cpu: bool = False) -> Piano:
        if self.contaminato:
            raise ContrattoViolato(
                "invariante 7: cache contaminata da un errore, serve la pulizia esplicita")
        bpm = self.bytes_per_miss if bytes_per_miss is None else bytes_per_miss
        n_routes = len(ids)
        if k < 1 or rows < 1 or n_routes != k * rows:
            raise ContrattoViolato("forma degli ID incoerente con k*rows")
        if n_routes > self.n_slots:
            raise ContrattoViolato("n_routes oltre il numero di slot")
        for expert in ids:
            if not (0 <= expert < self.n_experts):
                raise ContrattoViolato(f"ID di route fuori intervallo: {expert}")
        if pesi is None:
            pesi = [1.0] * n_routes
        if len(pesi) != n_routes:
            raise ContrattoViolato("un peso per route")

        self._commit()
        stato_dopo_commit = self.istantanea()

        step = self.step_dispositivo
        self.step_dispositivo += 1
        epoca = (step + self.epoch_bias) >> 6
        clock_begin = self.clock_riservato
        self.clock_riservato += n_routes

        # 1) deduplica in ordine di prima comparsa (route_unique / unique_experts)
        unique_experts: list[int] = []
        indice_di: dict[int, int] = {}
        route_unique: list[int] = []
        for expert in ids:
            if expert not in indice_di:
                indice_di[expert] = len(unique_experts)
                unique_experts.append(expert)
            route_unique.append(indice_di[expert])
        n_unique = len(unique_experts)
        if n_unique > self.n_slots:
            raise ContrattoViolato("richieste uniche oltre il numero di slot")

        # 2) classificazione hit/miss sugli ID logici originali
        unique_slots = [self.slot_for_expert.get(e, -1) for e in unique_experts]
        for indice, slot in enumerate(unique_slots):
            if slot >= 0:
                if self.expert_for_slot[slot] != unique_experts[indice]:
                    raise ContrattoViolato("invariante 4: colpo su slot non reciproco")
                if self.slot_pronto[slot] is None or self.banche_scritte[slot] != 3:
                    raise ContrattoViolato("invariante 4: colpo su dato parziale")
        indici_miss = [i for i, s in enumerate(unique_slots) if s < 0]
        hits = n_unique - len(indici_miss)

        # 3) partizione CPU/GPU PRIMA dell'assegnazione degli slot e del gather
        quota = self.cpu_max if self.layer_eligible else 0
        # almeno un unico GPU deve restare, per avere uno slot alias valido
        n_cpu = max(0, min(quota, len(indici_miss), n_unique - 1))
        scelti = self._ordina_per_cpu(indici_miss, unique_experts, epoca)[:n_cpu]
        insieme_cpu = set(scelti)
        unique_is_cpu = [i in insieme_cpu for i in range(n_unique)]
        miss_cpu = [(i, unique_experts[i]) for i in sorted(insieme_cpu)]
        indici_miss_gpu = [i for i in indici_miss if i not in insieme_cpu]
        for _, expert in miss_cpu:
            if self.slot_for_expert.get(expert, -1) != -1:
                raise ContrattoViolato("invariante 2: esperto CPU risulta residente")

        # 4) assegnazione degli slot ai soli miss GPU
        protetti = {s for s in unique_slots if s >= 0}
        vittime: list[int] = []
        miss_gpu: list[tuple[int, int, int]] = []
        for indice in indici_miss_gpu:
            slot = self._scegli_vittima(protetti, epoca)
            vittime.append(self.expert_for_slot[slot])
            unique_slots[indice] = slot
            protetti.add(slot)
            miss_gpu.append((indice, unique_experts[indice], slot))
            # il gather del piano corrente scrive le tre banche prima del consumo
            self.banche_scritte[slot] = 3
            self.slot_pronto[slot] = self.n_piani

        # 5) alias a peso zero per le route CPU
        alias_slot = -1
        for indice in range(n_unique):
            if not unique_is_cpu[indice]:
                alias_slot = unique_slots[indice]
                break
        if n_cpu and (alias_slot < 0 or alias_slot not in protetti):
            raise ContrattoViolato("alias CPU senza una route GPU reale e protetta")
        remapped_ids = []
        pesi_gpu = []
        job_cpu = []
        for route, expert in enumerate(ids):
            indice = route_unique[route]
            if unique_is_cpu[indice]:
                remapped_ids.append(alias_slot)
                pesi_gpu.append(0.0)
                job_cpu.append((route // k, expert, pesi[route]))
            else:
                slot = unique_slots[indice]
                if slot < 0:
                    raise ContrattoViolato("route GPU senza slot")
                remapped_ids.append(slot)
                pesi_gpu.append(pesi[route])
        for slot in set(remapped_ids):
            if self.slot_pronto[slot] is None or self.slot_pronto[slot] > self.n_piani:
                raise ContrattoViolato("invariante 4: consumo di uno slot non pronto")

        piano = Piano(indice=self.n_piani, step=step, epoca=epoca, k=k, rows=rows,
                      n_routes=n_routes, ids=list(ids), pesi=list(pesi),
                      unique_experts=unique_experts, route_unique=route_unique,
                      unique_slots=unique_slots, unique_is_cpu=unique_is_cpu,
                      hits=hits, miss_gpu=miss_gpu, miss_cpu=miss_cpu,
                      vittime=vittime, remapped_ids=remapped_ids, pesi_gpu=pesi_gpu,
                      job_cpu=job_cpu, alias_slot=alias_slot, bytes_per_miss=bpm,
                      clock_begin=clock_begin, stato_dopo_commit=stato_dopo_commit)
        self._verifica_invarianti(piano)

        if fallisci_job_cpu:
            # Invariante 7: la richiesta e' invalida, il piano non viene ammesso
            # e nessuno zero viene restituito come risultato. Il gather del piano
            # corrente ha pero' gia' sovrascritto gli slot assegnati: il vecchio
            # residente di quegli slot NON e' piu' valido e va rimosso dalla
            # mappatura. Finche' non si esegue la pulizia esplicita la cache e'
            # contaminata e nessun altro piano puo' usarla.
            for _, _, slot in miss_gpu:
                self.banche_scritte[slot] = 0
                self.slot_pronto[slot] = None
                vecchio = self.expert_for_slot[slot]
                if vecchio >= 0:
                    del self.slot_for_expert[vecchio]
                    self.expert_for_slot[slot] = -1
                    self.last_used[slot] = 0
            self.contaminato = True
            raise JobCpuFallito("job CPU fallito: piano scartato senza ammissioni")

        self.pending = piano
        self.n_piani += 1
        self._aggiorna_contatori(piano)
        return piano

    # ------------------------------------------------------------- meccanismi
    def _ordina_per_cpu(self, indici_miss, unique_experts, epoca):
        if self.cpu_order == "route":
            return list(indici_miss)
        if self.cpu_order == "last":
            return list(reversed(indici_miss))
        if self.cpu_order == "expert":
            return sorted(indici_miss, key=lambda i: (unique_experts[i], i))
        efficaci = {}
        for i in indici_miss:
            e = unique_experts[i]
            efficaci[i] = frequenza_efficace(self.freq[e], self.epoch_of[e], epoca)
        segno = 1 if self.cpu_order == "freq" else -1
        return sorted(indici_miss, key=lambda i: (segno * efficaci[i], i))

    def _scegli_vittima(self, protetti: set[int], epoca: int) -> int:
        migliore = None
        for slot in range(self.n_slots):
            if slot in protetti:
                continue
            residente = self.expert_for_slot[slot]
            freq = 0
            if self.frequency_aware and residente >= 0:
                freq = frequenza_efficace(self.freq[residente], self.epoch_of[residente], epoca)
            chiave = (freq, self.last_used[slot], slot)
            if migliore is None or chiave < migliore:
                migliore = chiave
        if migliore is None:
            raise ContrattoViolato("nessuno slot sfrattabile: le richieste superano gli slot")
        return migliore[2]

    def _verifica_invarianti(self, piano: Piano) -> None:
        # 1: richieste uniche = hit GPU + miss GPU + miss CPU
        if piano.n_unique != piano.hits + piano.n_miss_gpu + piano.n_miss_cpu:
            raise ContrattoViolato("invariante 1: la somma degli insiemi non torna")
        # 1-bis: le coppie token/esperto sono una contabilita' separata
        coppie = [(r // piano.k, e) for r, e in enumerate(piano.ids)]
        if len(coppie) != piano.n_routes:
            raise ContrattoViolato("invariante 1: coppie token/esperto incoerenti")
        if len(set(coppie)) != len(coppie):
            raise ContrattoViolato("invariante 5: coppia token/esperto ripetuta")
        # 2: nessuna ammissione fittizia per gli esperti CPU
        esperti_cpu = {e for _, e in piano.miss_cpu}
        if esperti_cpu & {e for _, e, _ in piano.miss_gpu}:
            raise ContrattoViolato("invariante 2: esperto sia CPU sia ammesso")
        if esperti_cpu & set(piano.vittime):
            raise ContrattoViolato("invariante 2: esperto CPU fra le vittime")
        # 3: contabilita' logica completa, recenza solo sugli slot validi
        if piano.n_miss_cpu and all(not f for f in piano.unique_is_cpu):
            raise ContrattoViolato("invariante 3: insieme CPU non marcato")
        # 4: la vittima non e' mai un colpo corrente ne' uno slot gia' assegnato
        indici_miss_gpu = {i for i, _, _ in piano.miss_gpu}
        esperti_colpo = {piano.unique_experts[i] for i in range(piano.n_unique)
                         if not piano.unique_is_cpu[i] and i not in indici_miss_gpu}
        if esperti_colpo & set(v for v in piano.vittime if v >= 0):
            raise ContrattoViolato("invariante 4: sfrattato un colpo corrente")
        slot_assegnati = [s for _, _, s in piano.miss_gpu]
        if len(set(slot_assegnati)) != len(slot_assegnati):
            raise ContrattoViolato("invariante 4: due miss sullo stesso slot")
        for indice, _, slot in piano.miss_gpu:
            if piano.unique_slots[indice] != slot:
                raise ContrattoViolato("invariante 4: slot assegnato non registrato")
        slot_correnti = {s for s in piano.unique_slots if s >= 0}
        if len(slot_correnti) != piano.n_unique - piano.n_miss_cpu:
            raise ContrattoViolato("invariante 4: slot distinti diversi dagli unici GPU")
        # 5: ogni coppia contribuisce una volta sola con il peso originale
        pesi_cpu = {}
        for route, (token, expert, peso) in zip(
                [r for r in range(piano.n_routes) if piano.unique_is_cpu[piano.route_unique[r]]],
                piano.job_cpu):
            if (token, expert) != coppie[route]:
                raise ContrattoViolato("invariante 5: job CPU non allineato alla route")
            pesi_cpu[route] = peso
        for route in range(piano.n_routes):
            atteso = piano.pesi[route]
            cpu = pesi_cpu.get(route)
            gpu = piano.pesi_gpu[route]
            if cpu is None:
                if gpu != atteso:
                    raise ContrattoViolato("invariante 5: peso GPU alterato")
            else:
                if gpu != 0.0:
                    raise ContrattoViolato("invariante 5: route CPU con peso GPU non nullo")
                if cpu != atteso:
                    raise ContrattoViolato("invariante 5: peso CPU diverso dall'originale")
        # Nessuna rinormalizzazione dei pesi GPU rimanenti: il multiinsieme dei
        # contributi e' identico bit per bit a quello dei pesi originali. Il
        # confronto e' sul multiinsieme e non su una somma, perche' una somma
        # dipenderebbe dall'ordine di addizione in virgola mobile.
        contributi = [pesi_cpu[r] if r in pesi_cpu else piano.pesi_gpu[r]
                      for r in range(piano.n_routes)]
        if contributi != piano.pesi:
            raise ContrattoViolato("invariante 5: contributo diverso dal peso originale")

    def _aggiorna_contatori(self, piano: Piano) -> None:
        c = self.contatori
        c["plans"] += 1
        c["unique_requests"] += piano.n_unique
        c["gpu_hits"] += piano.hits
        c["gpu_misses"] += piano.n_miss_gpu
        c["cpu_misses"] += piano.n_miss_cpu
        c["pairs_total"] += piano.n_routes
        c["pairs_cpu"] += len(piano.job_cpu)
        c["bytes_loaded"] += piano.n_miss_gpu * piano.bytes_per_miss
        c["victims_evicted"] += sum(1 for v in piano.vittime if v >= 0)

    # ------------------------------------------------------------- istantanea
    def istantanea(self) -> dict:
        ordine = sorted(range(self.n_slots), key=lambda s: (self.last_used[s], s))
        return {
            "expert_for_slot": tuple(self.expert_for_slot),
            "slot_for_expert": tuple(sorted(self.slot_for_expert.items())),
            "freq": tuple(sorted((e, f) for e, f in self.freq.items() if f)),
            "epoch_of": tuple(sorted((e, v) for e, v in self.epoch_of.items()
                                     if self.freq.get(e))),
            "ordine_recenza": tuple(ordine),
        }


def istantanea_riferimento(cache) -> dict:
    """Stessa forma di `CacheCpuGpu.istantanea` per la classe di riferimento."""
    ordine = sorted(range(cache.n), key=lambda s: (cache.last[s], s))
    return {
        "expert_for_slot": tuple(cache.expert_for),
        "slot_for_expert": tuple(sorted(cache.slot_for.items())),
        "freq": tuple(sorted((e, f) for e, f in cache.freq.items() if f)),
        "epoch_of": tuple(sorted((e, v) for e, v in cache.epoch_of.items()
                                 if cache.freq.get(e))),
        "ordine_recenza": tuple(ordine),
    }


def pesi_sintetici(step: int, n_routes: int) -> list[float]:
    """Pesi deterministici e non uniformi: la traccia storica non registra i
    pesi del router, quindi qui si verifica solo la CONTABILITA' dei pesi, non
    un valore numerico del modello. Una route per piano ha peso esattamente 0."""
    pesi = []
    for route in range(n_routes):
        valore = ((step * 2654435761 + route * 40503) % 9973) / 9973.0
        pesi.append(0.0 if route == step % n_routes else valore)
    return pesi
