#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P4 - genera i preset delle celle a partire da `preset_A_p3.json`.

I preset si scrivono in Python e senza BOM: `ConvertTo-Json | Set-Content
-Encoding utf8` di PowerShell ne mette uno e `json.load` lo rifiuta (difetto 4
di P3, un blocco intero perso dopo 211 s di caricamento del modello).

Ogni preset dichiara ESPLICITAMENTE tutte le opzioni dell'ibrido, comprese le
tre nuove di P4: un valore ereditato dalla sessione non puo' falsare una cella.

    python genera_preset_p4.py
"""
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"
BASE = BANCO / "preset_A_p3.json"

# I 47 strati ammessi: tutti tranne il 2 (gate/up IQ3_S, escluso da D07).
STRATI_47 = ",".join(str(i) for i in range(48) if i != 2)

# cella -> (etichetta, descrizione, opzioni dell'ibrido che cambiano)
CELLE = [
    ("C0", "p4_c0_spento",
     "RIFERIMENTO. Ibrido spento, stessa build di tutte le altre celle. "
     "Rimisurato oggi per avere la coppia a macchina uguale.",
     {"LLAMA_MOE_CPU": "0", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C1", "p4_c1_impianto_strato1",
     "IMPIANTO COMPLETO A CPU SPENTA su un solo strato: export, submit, wait, "
     "guardia e add esistono, ma cpu_max=0 e nessuna route viene deviata. "
     "E' la misura A1 aperta da P3 §9: separa impianto da calcolo.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C2", "p4_c2_solo_submit_strato1",
     "Come C1 ma SENZA il nodo host `wait`: resta un solo nodo host (submit) e, "
     "poiche' i due non sono entrambi accesi, i hook sono INERTI. Misura il "
     "costo della sola consegna di UNA callback al driver.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "27", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C3", "p4_c3_solo_wait_strato1",
     "Come C1 ma SENZA il nodo host `submit`: resta il solo `wait`, con hook "
     "inerti. Confronto con C2: il costo di un nodo host dipende da quale?",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "29", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C4", "p4_c4_diagnostica_strato1",
     "DIAGNOSTICA sullo strato 1, cpu_max=2, contatori spenti. Meccanismo "
     "completo compreso il calcolo CPU, senza risparmio di byte. E' il lato D "
     "di P3, rimisurato con i binari di P4.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C5", "p4_c5_diagnostica_senza_calcolo_strato1",
     "Come C4 ma il pool ACCETTA il job e scrive subito un contributo zero, "
     "senza aritmetica. C4 - C5 = costo del CALCOLO CPU. In diagnostica `y` "
     "viene comunque azzerata dalla guardia: l'uscita non cambia.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "1",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C6", "p4_c6_attiva_strato1",
     "ATTIVA sullo strato 1, cpu_max=2: il candidato B di P3, rimisurato con i "
     "binari di P4. Le impronte cambiano (rischio R10), come in P3.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    # C7 e C8 (attiva a sei e a due thread) non esistono come preset separati:
    # la sensibilita' ai core si misura meglio in DIAGNOSTICA, dove il carico e
    # il testo non cambiano da cella a cella (C18/C17/C4/C16 = 1/2/4/6 thread).
    # In modalita' attiva bastano i due estremi utili: C6 (quattro thread, il
    # candidato di P3) e C20 (due thread, il candidato corretto). Una corsa
    # attiva a sei thread avrebbe solo confermato C16 pagando cinque minuti.

    # --------------------------------------------------------------- amplificate
    # Su UN solo strato ogni pezzo del meccanismo vale decimi di millisecondo:
    # sotto il rumore del profilo `fumo` (~0,5%, cioe' ~0,2 ms/token). Le celle
    # C10-C15 accendono lo stesso pezzo su 47 strati: il segnale si moltiplica
    # per 47 e il costo per strato si legge dividendo. Con cpu_max=0 l'uscita
    # del modello non cambia, quindi le impronte restano un oracolo anche qui.
    ("C10", "p4_c10_47strati_nessun_nodo",
     "AMPLIFICATA, 47 strati. Nessun pezzo acceso: restano solo i pesi di "
     "routing agganciati a src[4] del mul_mat_id e il pool fermo. E' il "
     "riferimento della scala amplificata.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "0", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C11", "p4_c11_47strati_add",
     "AMPLIFICATA, 47 strati: + il nodo `add` (47 nodi in piu' nel graph). "
     "C11 - C10 = costo dell'add e dell'eventuale fusione rotta (apertura A4).",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "16", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C12", "p4_c12_47strati_add_export",
     "AMPLIFICATA, 47 strati: + il kernel di export. C12 - C11 = costo del "
     "kernel di export.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "17", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C13", "p4_c13_47strati_add_export_guardia",
     "AMPLIFICATA, 47 strati: + la guardia del merge. C13 - C12 = costo della "
     "guardia.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "25", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C14", "p4_c14_47strati_un_nodo_host",
     "AMPLIFICATA, 47 strati: + UN nodo host (submit) con hook INERTI. "
     "C14 - C13 = costo di 47 cudaLaunchHostFunc con callback che ritorna "
     "subito, cioe' il prezzo del solo meccanismo di callback.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "27", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    # ------------------------------------------------- sensibilita' ai core
    # Il confronto si fa in DIAGNOSTICA e non in modalita' attiva: la
    # diagnostica non cambia la traiettoria ne' il testo, quindi il carico e'
    # identico cella per cella e l'impronta resta un oracolo. In modalita'
    # attiva il testo cambia e i casi hanno lunghezze diverse.
    ("C16", "p4_c16_diagnostica_6core",
     "Come C4 (diagnostica, strato 1) con sei thread nel pool. C4 - C16 dice "
     "se il costo del calcolo CPU scala con i core (compute-bound) o no "
     "(latenza di risveglio / contesa, rischio R7).",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "6"}),

    ("C17", "p4_c17_diagnostica_2core",
     "Come C4 con due thread nel pool.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "2"}),

    ("C18", "p4_c18_diagnostica_1core",
     "Come C4 con UN solo thread. Con uno, due, quattro e sei si legge la "
     "curva: se il tempo non si dimezza passando da uno a due, il collo non e' "
     "l'aritmetica.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "1"}),

    ("C19", "p4_c19_diagnostica_max1",
     "Come C4 con cpu_max=1: UN solo esperto CPU per strato. Il calcolo si "
     "dimezza; se il tempo non si dimezza, meta' del costo e' latenza fissa.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "1",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),

    ("C20", "p4_c20_attiva_strato1_2core",
     "IL CANDIDATO CORRETTO: attiva sullo strato 1, cpu_max=2, con DUE thread "
     "nel pool invece di quattro. La curva C18/C17/C4/C16 dice che quattro "
     "thread sono il difetto, non l'aritmetica.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "2"}),

    ("C21", "p4_c21_attiva_strato1_2core_contatori",
     "VERIFICA, non una misura di tempo: come C20 con i contatori accesi "
     "(LLAMA_MOE_CPU_REPORT=64, che fa un cudaDeviceSynchronize). Serve a "
     "provare che il ramo CPU e' davvero partito, che l'invariante 1 tiene, "
     "che non ci sono NaN e che il graph non viene ricatturato.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "2",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "2", "LLAMA_MOE_CPU_REPORT": "64"}),

    ("C22", "p4_c22_diagnostica_2core_max1",
     "Diagnostica, due thread, UN solo esperto CPU. Con C17 (due thread, due "
     "esperti) da' la scala dell'aritmetica a parita' di rendezvous.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": "1", "LLAMA_MOE_CPU_MAX": "1",
      "LLAMA_MOE_CPU_DIAG": "1", "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "2"}),

    ("C15", "p4_c15_47strati_impianto_completo",
     "AMPLIFICATA, 47 strati: impianto completo, hook VERI (submit pubblica, "
     "wait attende). C15 - C14 = costo del secondo nodo host PIU' il "
     "giro completo di risveglio del pool.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_LAYERS": STRATI_47, "LLAMA_MOE_CPU_MAX": "0",
      "LLAMA_MOE_CPU_DIAG": "0", "LLAMA_MOE_CPU_ALLOW_ZERO": "1",
      "LLAMA_MOE_CPU_NODES": "31", "LLAMA_MOE_CPU_NOCOMPUTE": "0",
      "LLAMA_MOE_CPU_THREADS": "4"}),
]

OPZIONI_IBRIDO = ("LLAMA_MOE_CPU", "LLAMA_MOE_CPU_LAYERS", "LLAMA_MOE_CPU_MAX",
                  "LLAMA_MOE_CPU_DIAG", "LLAMA_MOE_CPU_THREADS", "LLAMA_MOE_CPU_REPORT",
                  "LLAMA_MOE_CPU_WAIT_US", "LLAMA_MOE_CPU_ACK_US",
                  "LLAMA_MOE_CPU_ALLOW_ZERO", "LLAMA_MOE_CPU_NODES",
                  "LLAMA_MOE_CPU_NOCOMPUTE")


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    scritti = []
    for cella, etichetta, descr, env in CELLE:
        p = json.loads(json.dumps(base))   # copia profonda
        p["id"] = cella + "_p4"
        p["etichetta"] = etichetta
        p["fase"] = "P4"
        p["descrizione"] = descr
        # i contatori fanno un cudaDeviceSynchronize: MAI dentro una misura
        p["env"]["LLAMA_MOE_CPU_REPORT"] = "0"
        p["env"]["LLAMA_MOE_CPU_WAIT_US"] = "2000000"
        p["env"]["LLAMA_MOE_CPU_ACK_US"] = "200000"
        p["env"].update(env)
        mancanti = [k for k in OPZIONI_IBRIDO if k not in p["env"]]
        assert not mancanti, "opzioni non dichiarate: %s" % mancanti
        p["differenze_dal_lato_B"] = "cella %s di P4: %s" % (cella, descr)
        out = BANCO / ("preset_%s_p4.json" % cella)
        out.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
        assert out.read_bytes()[:1] == b"{", "BOM nel preset %s" % out
        scritti.append(out.name)
    print("scritti %d preset:" % len(scritti))
    for n in scritti:
        print("  " + n)


if __name__ == "__main__":
    main()
