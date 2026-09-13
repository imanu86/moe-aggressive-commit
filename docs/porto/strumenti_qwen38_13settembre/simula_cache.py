"""Simula la cache esperti di Qwen38 (politica di moe_grouped_plan_decode) sulle rotte catturate.

Per strato: 64 slot; a ogni chiamata gli esperti unici del batch non residenti vengono caricati,
sfrattando fra gli slot NON usati nella chiamata quello a frequenza efficace minima, poi il piu' vecchio,
poi l'indice minore. Frequenza: +1 per uso, dimezzata ogni 64 chiamate (epoch = step >> 6).

Scenari (stessa sequenza di token, accettazione della bozza pseudo-casuale fissa):
  S0      nessuna bozza: batch {t}
  GPU-n   bozza a n token tutta su GPU: batch {t..t+n}, tutto ammesso in cache
  CPU-n   bozza a n token: righe di bozza -> esperti residenti o gia' nel batch su GPU,
          gli altri calcolati sulla CPU (non ammessi, non contano in frequenza)
"""
import argparse, collections, json, random, struct, pathlib

ap = argparse.ArgumentParser()
ap.add_argument('--routes', default=str(pathlib.Path(__file__).with_name('routes.bin')))
ap.add_argument('--slots', type=int, default=64)
ap.add_argument('--accept', type=float, default=0.75)
ap.add_argument('--warm', type=int, default=64)
args = ap.parse_args()

raw = pathlib.Path(args.routes).read_bytes()
routes = collections.defaultdict(dict)  # layer -> step -> ids
off = 0
while off + 16 <= len(raw):
    step, layer, k, rows = struct.unpack_from('<4i', raw, off); off += 16
    ids = struct.unpack_from(f'<{k*rows}i', raw, off); off += 4 * k * rows
    routes[layer][step] = list(ids[:k])
layers = sorted(routes)
steps = min(len(routes[l]) for l in layers)
print(f'strati {len(layers)}, token {steps}, k {len(routes[layers[0]][0])}')


class Cache:
    def __init__(self, n_slots):
        self.n = n_slots
        self.slot_for = {}
        self.expert_for = [-1] * n_slots
        self.last = [0] * n_slots
        self.freq = collections.defaultdict(int)
        self.epoch_of = collections.defaultdict(int)
        self.step = 0
        self.clock = 0

    def eff(self, e, epoch):
        el = epoch - self.epoch_of[e]
        return self.freq[e] >> el if el < 32 else 0

    def call(self, experts):
        """experts: lista ordinata di esperti unici caricati su GPU in questa chiamata. Ritorna i miss."""
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
        return len(misses)


def unique(seq):
    seen, out = set(), []
    for e in seq:
        if e not in seen:
            seen.add(e); out.append(e)
    return out


def run(n_draft, cpu_lane):
    rng = random.Random(1234)
    caches = {l: Cache(args.slots) for l in layers}
    t = 0
    cycles = emitted = 0
    gpu_miss = 0          # esperti trasferiti (somma su strati)
    cpu_experts = 0      # esperti calcolati sulla CPU (somma su strati)
    cpu_per_layer = []   # per ciclo, per strato
    counted = False
    while t + n_draft < steps:
        counted = t >= args.warm
        rows = [t + j for j in range(n_draft + 1)]
        cyc_cpu = 0
        cyc_miss = 0
        for l in layers:
            c = caches[l]
            main = unique(routes[l][rows[0]])
            if not cpu_lane:
                batch = unique(sum((routes[l][r] for r in rows), []))
                cyc_miss += c.call(batch)
            else:
                gpu = list(main)
                gset = set(gpu)
                cpu_here = 0
                for r in rows[1:]:
                    for e in routes[l][r]:
                        if e in gset:
                            continue
                        if e in c.slot_for:
                            gpu.append(e); gset.add(e)
                        else:
                            cpu_here += 1
                cyc_miss += c.call(gpu)
                cyc_cpu += cpu_here
                if counted:
                    cpu_per_layer.append(cpu_here)
        # accettazione: ogni posizione accettata con prob. args.accept, stop al primo rifiuto
        acc = 0
        for _ in range(n_draft):
            if rng.random() < args.accept:
                acc += 1
            else:
                break
        if counted:
            cycles += 1; emitted += 1 + acc
            gpu_miss += cyc_miss; cpu_experts += cyc_cpu
        t += 1 + acc
    res = {'n_draft': n_draft, 'cpu_lane': cpu_lane, 'cicli': cycles,
           'token_per_ciclo': round(emitted / cycles, 3),
           'trasferiti_per_ciclo': round(gpu_miss / cycles, 1),
           'trasferiti_per_strato': round(gpu_miss / cycles / len(layers), 2)}
    if cpu_lane:
        cpl = sorted(cpu_per_layer)
        res.update({'cpu_per_ciclo': round(cpu_experts / cycles, 1),
                    'cpu_per_strato_medio': round(cpu_experts / cycles / len(layers), 2),
                    'cpu_per_strato_p90': cpl[int(len(cpl) * 0.9)], 'cpu_per_strato_max': cpl[-1]})
    return res


out = [run(0, False)]
for n in (1, 2, 3):
    out.append(run(n, False))
    out.append(run(n, True))
for r in out:
    print(json.dumps(r, ensure_ascii=False))
pathlib.Path(args.routes).with_suffix('.sim.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
