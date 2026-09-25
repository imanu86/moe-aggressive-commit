"""Testa MTP "condivisa" per Qwen3.6-35B-A3B (25/9): copia del GGUF MTP separato SENZA token_embd e output.

La testa Q8_0 di ggml-org porta con se' una copia Q8_0 di token_embd e output (515 MiB l'una). Con il runtime
elastico Q36s la testa senza quei tensori usa embedding e LM head del bersaglio (ctx_other), come la testa
condivisa di Flash-Next: niente output duplicato in VRAM e passo della bozza piu' leggero (LM head del
bersaglio Q6_K 398 MiB invece di Q8_0 515 MiB). Il file di partenza non viene toccato.
Uso: python crea_testa_condivisa.py SORGENTE.gguf DESTINAZIONE.gguf
"""
import sys
from pathlib import Path

import gguf

TOGLI = {"token_embd.weight", "output.weight"}

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    sys.exit(f"ERRORE: {dst} esiste gia', non sovrascrivo")
reader = gguf.GGUFReader(src)
arch = reader.fields[gguf.Keys.General.ARCHITECTURE].contents()
writer = gguf.GGUFWriter(dst, arch=arch, endianess=reader.endianess)
al = reader.fields.get(gguf.Keys.General.ALIGNMENT)
if al is not None:
    writer.data_alignment = al.contents()

for field in reader.fields.values():
    if field.name == gguf.Keys.General.ARCHITECTURE or field.name.startswith("GGUF."):
        continue
    val_type = field.types[0]
    sub_type = field.types[-1] if val_type == gguf.GGUFValueType.ARRAY else None
    valore = field.contents()
    if field.name == gguf.Keys.General.NAME:
        valore = str(valore) + " (testa MTP condivisa: senza token_embd/output)"
    writer.add_key_value(field.name, valore, val_type, sub_type=sub_type)

tenuti = [t for t in reader.tensors if t.name not in TOGLI]
tolti = [t.name for t in reader.tensors if t.name in TOGLI]
assert sorted(tolti) == sorted(TOGLI), f"attesi {sorted(TOGLI)}, trovati {tolti}"
for t in tenuti:
    writer.add_tensor_info(t.name, t.data.shape, t.data.dtype, t.data.nbytes, t.tensor_type)
writer.write_header_to_file()
writer.write_kv_data_to_file()
writer.write_ti_data_to_file()
for t in tenuti:
    writer.write_tensor_data(t.data, tensor_endianess=reader.endianess)
writer.close()
print(f"{dst}: {len(tenuti)} tensori, tolti {tolti}, {dst.stat().st_size / 2**20:.1f} MiB "
      f"(sorgente {src.stat().st_size / 2**20:.1f} MiB)")
