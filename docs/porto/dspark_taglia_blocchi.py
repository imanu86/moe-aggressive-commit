"""
DSpark a UN SOLO BLOCCO — versione 2.

La v1 falliva al caricamento: `dflash.swiglu_clamp_exp has wrong array length;
expected 1, got 3`. Il difetto era mio: avevo cambiato `block_count` ma copiato
tal quali gli ARRAY PER-BLOCCO, che restavano di lunghezza 3.

Regola generale applicata qui: **ogni campo array la cui lunghezza e' uguale al
numero di blocchi e' un array per-blocco e va troncato al primo elemento.**
Gli array di altra lunghezza (vocabolario, token) non si toccano.
"""

import sys, os, hashlib
sys.path.insert(0, r'D:\llama-dspark\gguf-py')
import gguf
import numpy as np

SRC = r'D:\ds4-models\DSpark-draft-Q2K.gguf'
DST = r'D:\ds4-models\DSpark-draft-Q2K-blk1.gguf'
TIENI = 0

r = gguf.GGUFReader(SRC, 'r')
arch = bytes(r.fields['general.architecture'].parts[r.fields['general.architecture'].data[0]]).decode()
campo_blocchi = [k for k in r.fields if k.endswith('.block_count')][0]
n_blocchi = int(r.fields[campo_blocchi].parts[r.fields[campo_blocchi].data[0]][0])
print('architettura %s | blocchi %d' % (arch, n_blocchi))

# --- trova TUTTI gli array per-blocco (lunghezza == n_blocchi) ---
per_blocco = []
for k in r.fields:
    f = r.fields[k]
    if len(f.types) > 1 and f.types[0] == gguf.GGUFValueType.ARRAY and len(f.data) == n_blocchi:
        per_blocco.append(k)
print('array per-blocco trovati (%d):' % len(per_blocco))
for k in per_blocco:
    print('   %-34s %s' % (k, list(r.fields[k].contents())))

tenuti = [t for t in r.tensors
          if (not t.name.startswith('blk.')) or int(t.name.split('.')[1]) == TIENI]
print('tensori: tengo %d su %d' % (len(tenuti), len(r.tensors)))

w = gguf.GGUFWriter(DST, arch)
cambiati = []
for k in r.fields:
    if k in ('GGUF.version', 'GGUF.tensor_count', 'GGUF.kv_count', 'general.architecture'):
        continue
    f = r.fields[k]
    if k == campo_blocchi:
        w.add_uint32(k, 1); cambiati.append(k + ' -> 1'); continue
    if k in per_blocco:
        v = list(f.contents())[TIENI:TIENI + 1]
        w.add_key_value(k, v, gguf.GGUFValueType.ARRAY, sub_type=f.types[1])
        cambiati.append('%s -> %s' % (k, v)); continue
    try:
        w.add_key_value(k, f.contents(), f.types[0],
                        sub_type=(f.types[1] if len(f.types) > 1 else None))
    except Exception as e:
        print('  !! campo non copiato:', k, e)

print('metadati cambiati:')
for c in cambiati:
    print('   ' + c)

# --- tensori CONCATENATI per blocco fuori da blk.N ---
# fc.weight e' [ne0=4096, ne1=12288] = 3 x 4096: e' un tensore per-blocco
# impacchettato, e il loader a 1 blocco ne pretende 4096. La quantizzazione
# Q2_K corre lungo ne0, quindi le righe sono indipendenti e affettare ne1 e'
# un taglio di byte pulito. Prendo la prima terza parte (stadio 0).
concatenati = {}
for t in tenuti:
    if t.name.startswith('blk.'):
        continue
    ne = [int(x) for x in t.shape if x > 0]
    # ne0 e' la dimensione VELOCE: se vale n_blocchi volte ne1, il tensore
    # impacchetta i blocchi lungo ne0 (caso di fc.weight: 12288 = 3 x 4096)
    if len(ne) > 1 and ne[0] == n_blocchi * ne[1]:
        concatenati[t.name] = ne
if concatenati:
    print('tensori concatenati per blocco (taglio su ne0):')
    for k, ne in concatenati.items():
        print('   %-24s ne=%s  ->  ne0 %d -> %d' % (k, ne, ne[0], ne[0] // n_blocchi))

for t in tenuti:
    if t.name in concatenati:
        ne = concatenati[t.name]
        raw = np.asarray(t.data).reshape(-1).view(np.uint8)
        righe = ne[1]
        per_riga = raw.size // righe
        assert per_riga % n_blocchi == 0, 'riga non divisibile: %s' % t.name
        tagliato = raw.reshape(righe, per_riga)[:, :per_riga // n_blocchi].copy()
        # raw_shape va data in BYTE e in ordine numpy: gguf la riconverte in
        # elementi dividendo per il type_size del quant (Q2_K = 84 B / 256 pesi)
        w.add_tensor(t.name, tagliato, raw_shape=list(tagliato.shape),
                     raw_dtype=t.tensor_type)
        print('   tagliato %s: %s -> %s byte' % (t.name, raw.size, tagliato.shape))
    else:
        w.add_tensor(t.name, np.asarray(t.data), raw_dtype=t.tensor_type)
w.write_header_to_file(); w.write_kv_data_to_file(); w.write_tensors_to_file(); w.close()
print('\nscritto: %s  (%.2f GB)' % (DST, os.path.getsize(DST) / (1024 ** 3)))

# ---------------- CANCELLI ----------------
print('\n=== CANCELLI ===')
v = gguf.GGUFReader(DST, 'r')
nomi = [t.name for t in v.tensors]
blocchi = sorted(set(int(x.split('.')[1]) for x in nomi if x.startswith('blk.')))
bc = int(v.fields[campo_blocchi].parts[v.fields[campo_blocchi].data[0]][0])
gb = os.path.getsize(DST) / (1024 ** 3)
esiti = []
esiti.append(('peso %.2f GB' % gb, 2.0 < gb < 2.6))
esiti.append(('blocchi %s' % blocchi, blocchi == [0]))
esiti.append(('block_count %d' % bc, bc == 1))
esiti.append(('tensori %d' % len(nomi), len(nomi) == len(tenuti)))
for k in per_blocco:
    L = len(v.fields[k].data)
    esiti.append(('%s lungo %d' % (k.split('.')[-1], L), L == 1))
def h(a): return hashlib.sha256(np.asarray(a).tobytes()).hexdigest()[:16]
srcmap = {t.name: t for t in r.tensors}
for t in ([x for x in v.tensors if 'exps' in x.name][:1] +
          [x for x in v.tensors if not x.name.startswith('blk.')][:2]):
    esiti.append(('%s bit-esatto' % t.name[:26], h(t.data) == h(srcmap[t.name].data)))
for n, ok in esiti:
    print('  %-34s %s' % (n, 'OK' if ok else '*** FALLITO ***'))
print('\nESITO:', 'TUTTI I CANCELLI PASSATI' if all(o for _, o in esiti) else 'QUALCOSA NON TORNA')
