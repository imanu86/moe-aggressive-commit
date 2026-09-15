# P7 cella 6 - genera i preset U4/U6(/U3) a partire da preset_T6_p7.json e
# preset_T7_p7.json (cella 5): stessa configurazione candidato "corsia accesa
# corretta", cambia solo LLAMA_MOE_CPU_THREADS. L'affinita' resta "auto": per
# n thread prende gli ULTIMI n core fisici (build_affinity(), moe_cpu_executor.cpp),
# cioe' esattamente "i core piu' lontani dal thread che accoda alla GPU" richiesto
# dal dispaccio (4 thread -> fisici 4-7, 6 thread -> fisici 2-7, 3 thread -> fisici 5-7).
#
# Per ogni N: un preset MAIN (REPORT=0, misura di tempo, come T6) e un preset
# CONTATORI (REPORT=64, NON una misura di tempo, come T7) per leggere esperti
# CPU/ciclo, byte risparmiati, invarianti, NaN.
#
# JSON senza BOM, indentazione 1, come i preset esistenti.
import io, json, os, collections, sys

QUI = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.abspath(os.path.join(QUI, "..", "banco_p0"))
BASE_MAIN = os.path.join(BANCO, "preset_T6_p7.json")
BASE_CONT = os.path.join(BANCO, "preset_T7_p7.json")

with io.open(BASE_MAIN, "r", encoding="utf-8") as f:
    base_main = json.load(f, object_pairs_hook=collections.OrderedDict)
with io.open(BASE_CONT, "r", encoding="utf-8") as f:
    base_cont = json.load(f, object_pairs_hook=collections.OrderedDict)

# n_thread -> (id, descrizione)
CELLE = [
    (4, "U4", "core fisici 4-7 (auto, ultimi 4)"),
    (6, "U6", "core fisici 2-7 (auto, ultimi 6)"),
    (3, "U3", "core fisici 5-7 (auto, ultimi 3)"),
]


def scrivi(base, ident, suffisso, descr_extra, n_thread, core_descr):
    p = json.loads(json.dumps(base), object_pairs_hook=collections.OrderedDict)
    etichetta = "p7c6_%s_mtp1_corsia_accesa_corretta_%dthread%s" % (
        ident.lower(), n_thread, ("_contatori" if suffisso == "C" else ""))
    descr = ("P7 cella 6 (prova A3', profilo fumo): %s. Come T6/T7 della cella 5 "
              "(corsia di bozza accesa, correzione A7, guardia MTP accesa) ma con "
              "LLAMA_MOE_CPU_THREADS=%d e LLAMA_MOE_CPU_AFFINITY=auto -> %s. %s") % (
        ("candidato, misura di tempo" if suffisso == "" else
         "CONTATORI: non e' una misura di tempo (sincronizzazione forzata)"),
        n_thread, core_descr, descr_extra)
    p["id"] = ident + suffisso + "_p7"
    p["etichetta"] = etichetta
    p["descrizione"] = descr
    p["fase"] = "P7-cella6"
    p["env"]["LLAMA_MOE_CPU_THREADS"] = str(n_thread)
    p["env"]["LLAMA_MOE_CPU_AFFINITY"] = "auto"
    p["differenze_dal_lato_B"] = "cella " + ident + suffisso + " di P7-cella6: " + descr
    dest = os.path.join(BANCO, "preset_" + ident + suffisso + "_p7.json")
    testo = json.dumps(p, ensure_ascii=False, indent=1)
    with io.open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(testo + "\n")
    print("scritto", dest)


solo = sys.argv[1:] if len(sys.argv) > 1 else None  # es: python genera_preset_p7c6.py U4 U6
for n_thread, ident, core_descr in CELLE:
    if solo and ident not in solo:
        continue
    scrivi(base_main, ident, "", "E' la corsa da cui si legge ciclo, R, t/s, accettazione.",
           n_thread, core_descr)
    scrivi(base_cont, ident, "C",
           "Da' esperti CPU/ciclo, byte risparmiati, route per riga, invarianti, non finiti.",
           n_thread, core_descr)
