#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4, seconda cella (ESTENSIONE) - genera i preset `preset_E<n>_p4.json`.

Come in P4-costo: i preset si scrivono in Python e senza BOM, perche'
`ConvertTo-Json | Set-Content -Encoding utf8` di PowerShell ne mette uno e
`json.load` lo rifiuta (difetto 4 di P3, un blocco perso dopo 211 s di
caricamento del modello).

Ogni preset dichiara ESPLICITAMENTE tutte e quindici le opzioni dell'ibrido,
comprese le quattro nuove dell'impianto leggero: un valore ereditato dalla
sessione non puo' falsare una cella.

    python genera_preset_p4e.py
"""
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"
BASE = BANCO / "preset_A_p3.json"

# I 47 strati supportati: tutti tranne il 2 (gate/up IQ3_S, escluso da D07).
TUTTI_47 = [i for i in range(48) if i != 2]

# Ordine per miss medi DECRESCENTI, calcolato da `trace64.jsonl` sul tratto
# caldo (step > 64, 703 piani per strato), strato 2 tolto. E' lo stesso conto
# della tabella di P3 §2, esteso a tutti i 47.
ORDINE_MISS = [0, 1, 12, 22, 7, 6, 38, 18, 34, 13, 21, 10, 28, 17, 29, 20,
               19, 37, 5, 14, 11, 8, 26, 30, 24, 33, 42, 4, 27, 35, 36, 25,
               9, 44, 45, 46, 3, 47, 41, 23, 16, 32, 43, 39, 40, 15, 31]
assert sorted(ORDINE_MISS) == sorted(TUTTI_47), "l'ordine dei miss non copre i 47 strati"

INSIEME_8 = sorted(ORDINE_MISS[:8])
INSIEME_24 = sorted(ORDINE_MISS[:24])
INSIEME_47 = sorted(ORDINE_MISS)


def elenco(strati):
    return ",".join(str(i) for i in strati)


# Impianto di P3 (il "prima" di ogni intervento) e impianto leggero (il "dopo").
PRIMA = {"LLAMA_MOE_CPU_FUSE": "0", "LLAMA_MOE_CPU_GUARD_LIGHT": "0",
         "LLAMA_MOE_CPU_THREADS": "4", "LLAMA_MOE_CPU_AFFINITY": "first"}
LEGGERO = {"LLAMA_MOE_CPU_FUSE": "1", "LLAMA_MOE_CPU_GUARD_LIGHT": "1",
           "LLAMA_MOE_CPU_THREADS": "2", "LLAMA_MOE_CPU_AFFINITY": "auto"}


def cella(env_extra, **kw):
    e = dict(PRIMA)
    e.update(kw.pop("impianto", {}))
    e.update(env_extra)
    return e


CELLE = []

CELLE.append(("E0", "p4e_e0_spento",
    "RIFERIMENTO. Ibrido spento, stessa build di tutte le altre celle della "
    "seconda cella di P4. Confrontabile con C0 di P4-costo (42,131 ms/token sul "
    "profilo fumo) e con il riferimento libero 24,44 t/s.",
    dict(PRIMA, **{"LLAMA_MOE_CPU": "0", "LLAMA_MOE_CPU_LAYERS": "1",
                   "LLAMA_MOE_CPU_MAX": "2", "LLAMA_MOE_CPU_DIAG": "0",
                   "LLAMA_MOE_CPU_ALLOW_ZERO": "0", "LLAMA_MOE_CPU_NODES": "31",
                   "LLAMA_MOE_CPU_NOCOMPUTE": "0"})))

# ---------------------------------------------------------------- A: impianto
# Scala AMPLIFICATA: lo stesso pezzo su 47 strati con cpu_max=0. Nessuna route
# viene deviata, `y` resta zero, l'uscita del modello NON cambia: le impronte
# devono restare identiche a E0 in tutte e quattro le celle, ed e' la prova che
# la misura e' dell'impianto e non di un'altra traiettoria.
AMPL = {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": elenco(INSIEME_47),
        "LLAMA_MOE_CPU_MAX": "0", "LLAMA_MOE_CPU_DIAG": "0",
        "LLAMA_MOE_CPU_ALLOW_ZERO": "1", "LLAMA_MOE_CPU_NODES": "31",
        "LLAMA_MOE_CPU_NOCOMPUTE": "0"}

CELLE.append(("E1", "p4e_e1_47strati_impianto_p3",
    "AMPLIFICATA, 47 strati, cpu_max=0: impianto di P3 tale e quale (due nodi "
    "host per strato, guardia che legge `y` sul PCIe, quattro thread sui primi "
    "core). E' il PRIMA dei tre interventi, e ripete la cella C15 di P4-costo "
    "(47,501 ms/token) con i binari nuovi.",
    dict(AMPL, **PRIMA)))

CELLE.append(("E2", "p4e_e2_47strati_un_nodo_host",
    "INTERVENTO 1: UN nodo host per strato invece di due. Il `submit` sparisce, "
    "la pubblicazione la fa il kernel di export e il pool si arma da solo. "
    "E2 - E1 = costo dei 47 nodi host tolti.",
    dict(AMPL, **dict(PRIMA, **{"LLAMA_MOE_CPU_FUSE": "1"}))))

CELLE.append(("E3", "p4e_e3_47strati_guardia_leggera",
    "INTERVENTO 2: la guardia del merge non legge piu' `y` dalla memoria host "
    "mappata (n_embd float per strato sul PCIe, con un solo blocco). Il "
    "controllo dei non finiti passa al pool, in memoria host. "
    "E3 - E2 = costo della lettura PCIe della guardia.",
    dict(AMPL, **dict(PRIMA, **{"LLAMA_MOE_CPU_FUSE": "1", "LLAMA_MOE_CPU_GUARD_LIGHT": "1"}))))

CELLE.append(("E4", "p4e_e4_47strati_impianto_leggero",
    "INTERVENTO 3: due thread invece di quattro, appuntati sugli ULTIMI core "
    "fisici invece che sui primi. E' l'impianto leggero completo a cpu_max=0. "
    "E4 - E3 = quanto pesa il pool quando non calcola nulla.",
    dict(AMPL, **LEGGERO)))

CELLE.append(("E4T3", "p4e_e4t3_47strati_impianto_leggero_3thread",
    "Come E4 con TRE thread nel pool invece di due: la prova 2/3 thread chiesta "
    "dall'incarico, fatta a cpu_max=0 dove il testo non cambia.",
    dict(AMPL, **dict(LEGGERO, **{"LLAMA_MOE_CPU_THREADS": "3"}))))

# --------------------------------------------------------------- B: estensione
# Impianto leggero, cpu_max=2, insiemi crescenti scelti per miss DECRESCENTI.
# Per ogni insieme due preset: uno con i contatori accesi (profilo `fumo`,
# VERIFICA e non misura di tempo: report_cpu fa un cudaDeviceSynchronize) e uno
# con i contatori spenti (profilo `solo_libero`, il candidato B di D14).
INSIEMI = [("8", INSIEME_8), ("24", INSIEME_24), ("47", INSIEME_47)]
for n, strati in INSIEMI:
    comune = dict(LEGGERO, **{"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": elenco(strati),
                              "LLAMA_MOE_CPU_MAX": "2", "LLAMA_MOE_CPU_DIAG": "0",
                              "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
                              "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0"})
    CELLE.append(("EV%s" % n, "p4e_ev%s_verifica_%sstrati" % (n, n),
        "VERIFICA (profilo fumo), NON una misura di tempo: %s strati attivi a "
        "cpu_max=2 con i contatori accesi (LLAMA_MOE_CPU_REPORT, che fa un "
        "cudaDeviceSynchronize). Serve a leggere invariante 1, NaN, byte "
        "risparmiati per strato e ricatture del graph." % n,
        dict(comune, **{"LLAMA_MOE_CPU_REPORT": "64"})))
    CELLE.append(("EB%s" % n, "p4e_eb%s_candidato_%sstrati" % (n, n),
        "CANDIDATO B (D14: prima il B): %s strati attivi a cpu_max=2 con "
        "l'impianto leggero e i contatori spenti. Si confronta col riferimento "
        "libero 24,44 t/s." % n,
        dict(comune, **{"LLAMA_MOE_CPU_REPORT": "0"})))

# cpu_max = 1 sull'insieme migliore: si decide a misura fatta quale sia, quindi
# i tre preset esistono tutti e se ne esegue uno solo.
for n, strati in INSIEMI:
    CELLE.append(("EM1_%s" % n, "p4e_em1_%sstrati_max1" % n,
        "Come EB%s ma con cpu_max=1: UN solo esperto CPU per strato. Meta' del "
        "risparmio di banda, meta' dell'aritmetica; si esegue solo "
        "sull'insieme risultato migliore." % n,
        dict(LEGGERO, **{"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": elenco(strati),
                         "LLAMA_MOE_CPU_MAX": "1", "LLAMA_MOE_CPU_DIAG": "0",
                         "LLAMA_MOE_CPU_ALLOW_ZERO": "0", "LLAMA_MOE_CPU_NODES": "31",
                         "LLAMA_MOE_CPU_NOCOMPUTE": "0", "LLAMA_MOE_CPU_REPORT": "0"})))

OPZIONI_IBRIDO = ("LLAMA_MOE_CPU", "LLAMA_MOE_CPU_LAYERS", "LLAMA_MOE_CPU_MAX",
                  "LLAMA_MOE_CPU_DIAG", "LLAMA_MOE_CPU_THREADS", "LLAMA_MOE_CPU_REPORT",
                  "LLAMA_MOE_CPU_WAIT_US", "LLAMA_MOE_CPU_ACK_US",
                  "LLAMA_MOE_CPU_ALLOW_ZERO", "LLAMA_MOE_CPU_NODES",
                  "LLAMA_MOE_CPU_NOCOMPUTE", "LLAMA_MOE_CPU_FUSE",
                  "LLAMA_MOE_CPU_GUARD_LIGHT", "LLAMA_MOE_CPU_AFFINITY",
                  "LLAMA_MOE_CPU_FUSE_SPIN_US")


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    scritti = []
    for id_cella, etichetta, descr, env in CELLE:
        p = json.loads(json.dumps(base))   # copia profonda
        p["id"] = id_cella + "_p4"
        p["etichetta"] = etichetta
        p["fase"] = "P4-estensione"
        p["descrizione"] = descr
        p["env"]["LLAMA_MOE_CPU_REPORT"] = "0"
        p["env"]["LLAMA_MOE_CPU_WAIT_US"] = "2000000"
        p["env"]["LLAMA_MOE_CPU_ACK_US"] = "200000"
        p["env"]["LLAMA_MOE_CPU_FUSE_SPIN_US"] = "0"
        p["env"].update(env)
        mancanti = [k for k in OPZIONI_IBRIDO if k not in p["env"]]
        assert not mancanti, "opzioni non dichiarate in %s: %s" % (id_cella, mancanti)
        p["differenze_dal_lato_B"] = "cella %s di P4-estensione: %s" % (id_cella, descr)
        out = BANCO / ("preset_%s_p4.json" % id_cella)
        out.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
        assert out.read_bytes()[:1] == b"{", "BOM nel preset %s" % out
        scritti.append(out.name)
    print("insieme 8  : %s" % elenco(INSIEME_8))
    print("insieme 24 : %s" % elenco(INSIEME_24))
    print("insieme 47 : %s" % elenco(INSIEME_47))
    print("scritti %d preset:" % len(scritti))
    for n in scritti:
        print("  " + n)


if __name__ == "__main__":
    main()
