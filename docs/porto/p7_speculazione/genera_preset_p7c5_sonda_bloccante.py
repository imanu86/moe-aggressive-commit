# P7 cella 5 - preset di SERVIZIO: T1C = T1B con CUDA_LAUNCH_BLOCKING=1.
#
# Non e' una misura: serve a far riportare l'errore CUDA dal lancio che lo
# produce invece che dal primo lancio successivo. Con il lancio bloccante il
# `CUDA_CHECK(cudaGetLastError())` che segue ogni kernel del nostro percorso
# nomina il file e la riga.
import io, json, os, collections

QUI = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.abspath(os.path.join(QUI, "..", "banco_p0"))
BASE = os.path.join(BANCO, "preset_T1B_p7.json")

with io.open(BASE, "r", encoding="utf-8") as f:
    p = json.load(f, object_pairs_hook=collections.OrderedDict)

p["id"] = "T1C_p7"
p["etichetta"] = "p7c5_t1c_diagnostica_lancio_bloccante"
p["descrizione"] = (
    "PRESET DI SERVIZIO, non una misura. T1B con CUDA_LAUNCH_BLOCKING=1: ogni lancio diventa "
    "sincrono, quindi l'errore viene riportato dal kernel che lo produce e non dal primo lancio "
    "successivo. Serve solo a nominare il kernel che va fuori dai limiti nella modalita "
    "diagnostica a due righe."
)
p["env"]["CUDA_LAUNCH_BLOCKING"] = "1"
p["differenze_dal_lato_B"] = "cella T1C di P7-cella5: " + p["descrizione"]

dest = os.path.join(BANCO, "preset_T1C_p7.json")
with io.open(dest, "w", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(p, ensure_ascii=False, indent=1) + "\n")
print("scritto", dest)
