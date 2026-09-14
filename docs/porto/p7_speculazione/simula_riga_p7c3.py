"""P7 cella 3 — simulazione della riga di verifica sulle rotte reali (routes.bin, 13/9).

Riproduce la politica esatta di moe_grouped_plan_decode (LRU consapevole della frequenza,
epoch = step >> 6, vittima scelta fra gli slot NON usati nella chiamata) e risponde a:

  1. byte trasferiti per ciclo a 1 / 2 / 3 righe  -> banda implicita contro i ms misurati
  2. quanto e' CONOSCIBILE al momento della testa:
     - copertura "ricorrenza" (gli esperti del ciclo precedente): quanti dei miss del
       ciclo corrente sarebbero stati portati da un prefetch che ripete il ciclo prima
     - oracolo: byte che un prefetch perfetto dovrebbe muovere nella finestra della testa
  3. finestra per strato: byte di miss per strato -> ms a banda PCIe misurata
"""
import argparse, collections, json, pathlib, random, struct

ap = argparse.ArgumentParser()
ap.add_argument('--routes', required=True)
ap.add_argument('--slots', type=int, default=64)
ap.add_argument('--accept', type=float, default=0.785)   # accettazione misurata M1
ap.add_argument('--warm', type=int, default=64)
ap.add_argument('--mib-per-expert', type=float, default=5676.85 / (64 * 48))
ap.add_argument('--gibs', type=float, default=21.5)      # banda del gather misurata
args = ap.parse_args()

raw = pathlib.Path(args.routes).read_bytes()
routes = collections.defaultdict(dict)
off = 0
while off + 16 <= len(raw):
    step, layer, k, rows = struct.unpack_from('<4i', raw, off); off += 16
    ids = struct.unpack_from(f'<{k*rows}i', raw, off); off += 4 * k * rows
    routes[layer][step] = list(ids[:k])
layers = sorted(routes)
steps = min(len(routes[l]) for l in layers)
K = len(routes[layers[0]][0])


class Cache:
    def __init__(self, n):
        self.n = n
        self.slot_for = {}
        self.expert_for = [-1] * n
        self.last = [0] * n
        self.freq = collections.defaultdict(int)
        self.epoch_of = collections.defaultdict(int)
        self.step = 0
        self.clock = 0

    def eff(self, e, epoch):
        el = epoch - self.epoch_of[e]
        return self.freq[e] >> el if el < 32 else 0

    def call(self, experts):
        self.step += 1
        epoch = self.step >> 6
        used = {self.slot_for[e] for e in experts if e in self.slot_for}
        misses = [e for e in experts if e not in self.slot_for]
        for e in misses:
            best = None
            for s in range(self.n):
                if s in used:
                    continue
                r = self.expert_for[s]
                f = 0 if r < 0 else self.eff(r, epoch)
                key = (f, self.last[s], s)
                if best is None or key < best[0]:
                    best = (key, s)
            s = best[1]
            old = self.expert_for[s]
            if old >= 0:
                del self.slot_for[old]
            self.expert_for[s] = e
            self.slot_for[e] = s
            used.add(s)
        for e in experts:
            self.clock += 1
            self.last[self.slot_for[e]] = self.clock
            f = self.eff(e, epoch)
            self.freq[e] = f + 1
            self.epoch_of[e] = epoch
        return misses


def unique(seq):
    seen, out = set(), []
    for e in seq:
        if e not in seen:
            seen.add(e); out.append(e)
    return out


def run(n_draft):
    rng = random.Random(1234)
    caches = {l: Cache(args.slots) for l in layers}
    prev_rows = None
    t = 0
    cycles = emitted = 0
    miss_tot = uniq_tot = 0
    # conoscibilita': dei miss del ciclo, quanti erano nelle rotte del ciclo PRECEDENTE
    known_prev = 0
    miss_per_layer = []
    miss_first_row = 0          # miss imputabili alla sola riga 1
    while t + n_draft < steps:
        counted = t >= args.warm
        rows = [t + j for j in range(n_draft + 1)]
        for l in layers:
            c = caches[l]
            batch = unique(sum((routes[l][r] for r in rows), []))
            miss = c.call(batch)
            if counted:
                miss_tot += len(miss)
                uniq_tot += len(batch)
                miss_per_layer.append(len(miss))
                if prev_rows is not None:
                    prev_set = set(sum((routes[l][r] for r in prev_rows), []))
                    known_prev += sum(1 for e in miss if e in prev_set)
        acc = 0
        for _ in range(n_draft):
            if rng.random() < args.accept:
                acc += 1
            else:
                break
        if counted:
            cycles += 1
            emitted += 1 + acc
        prev_rows = rows
        t += 1 + acc
    mib = miss_tot / cycles * args.mib_per_expert
    per_layer = sorted(miss_per_layer)
    return {
        'righe': n_draft + 1,
        'cicli': cycles,
        'token_per_ciclo': round(emitted / cycles, 3),
        'unici_per_strato': round(uniq_tot / cycles / len(layers), 2),
        'trasferiti_per_strato': round(miss_tot / cycles / len(layers), 2),
        'trasferiti_per_ciclo': round(miss_tot / cycles, 1),
        'MiB_per_ciclo': round(mib, 1),
        'ms_a_banda_misurata': round(mib / 1024 / args.gibs * 1000, 2),
        'MiB_per_strato': round(mib / len(layers), 2),
        'ms_per_strato': round(mib / len(layers) / 1024 / args.gibs * 1000, 3),
        'miss_gia_nel_ciclo_precedente_pct': round(100.0 * known_prev / max(1, miss_tot), 2),
        'miss_per_strato_p50': per_layer[len(per_layer) // 2],
        'miss_per_strato_p90': per_layer[int(len(per_layer) * 0.9)],
        'miss_per_strato_max': per_layer[-1],
    }


print(f'strati {len(layers)}, token {steps}, k {K}, MiB/esperto {args.mib_per_expert:.4f}, slot {args.slots}')
out = [run(n) for n in (0, 1, 2)]
for r in out:
    print(json.dumps(r, ensure_ascii=False))
base, one = out[0], out[1]
delta_mib = one['MiB_per_ciclo'] - base['MiB_per_ciclo']
print(json.dumps({
    'delta_MiB_riga_in_piu': round(delta_mib, 1),
    'delta_ms_a_banda_misurata': round(delta_mib / 1024 / args.gibs * 1000, 2),
}, ensure_ascii=False))
pathlib.Path('sim_riga_p7c3.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
