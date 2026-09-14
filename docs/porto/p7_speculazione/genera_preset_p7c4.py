"""P7, cella 4 — generatore dei preset S<n>.

Ogni preset dichiara ESPLICITAMENTE tutte le opzioni dell'ibrido, comprese le due
nuove (`LLAMA_MOE_CPU_POLL`, `LLAMA_MOE_CPU_POLL_US`): una cella misurata con la
configurazione sbagliata e' peggio di una cella non misurata.

Si parte dai preset gia' validati di P4-estensione (E0 per lo spento, E4 per
l'impianto leggero a 47 strati, EB8 per gli otto strati attivi) e si cambia solo
cio' che la cella richiede.

  python genera_preset_p7c4.py
"""
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"

STRATI_47 = ",".join(str(i) for i in range(48) if i != 2)
STRATI_8 = "0,1,6,7,12,18,22,38"

# ---------------------------------------------------------------- celle -----
# base: quale preset di P4-estensione si copia; poi le sole differenze di env.
CELLE = [
    ("S0", "E0", "p7c4_s0_spento",
     "RIFERIMENTO della cella 4. Ibrido spento, stessa build di tutte le altre celle. "
     "Rimisurato oggi perche' la build e' cambiata (P7-cella4) e il confronto va fatto a macchina uguale.",
     {}),
    ("S1", "E4", "p7c4_s1_47strati_nodo_host",
     "CONTROLLO. Impianto leggero di P4-estensione (UN nodo host per strato), 47 strati, cpu_max=0, "
     "sulla build nuova. Serve a provare che la build non ha spostato il riferimento di E4 (44,993 ms/token).",
     {"LLAMA_MOE_CPU_POLL": "0", "LLAMA_MOE_CPU_POLL_US": "50000"}),
    ("S2", "E4", "p7c4_s2_47strati_polling",
     "CELLA DEL CANCELLO. Impianto a POLLING: nessun nodo host, l'attesa e' il prologo della guardia. "
     "47 strati, cpu_max=0. Il cancello e' <= 15 us per strato, cioe' <= +0,705 ms/token su S0.",
     {"LLAMA_MOE_CPU_POLL": "1", "LLAMA_MOE_CPU_POLL_US": "50000"}),
    ("S3", "EB8", "p7c4_s3_8strati_polling",
     "CALIBRAZIONE del costo per strato ATTIVO con l'impianto a polling: 8 strati a cpu_max=2, "
     "profilo fumo (non solo_libero: qui serve il confronto omogeneo con S0/S1/S2, non un t/s).",
     {"LLAMA_MOE_CPU_POLL": "1", "LLAMA_MOE_CPU_POLL_US": "50000"}),
    ("S4", "EB8", "p7c4_s4_8strati_nodo_host",
     "CONTROLLO di S3: gli stessi 8 strati a cpu_max=2 con il NODO HOST. S3 - S4 e' il valore "
     "dell'intervento quando il pool calcola davvero.",
     {"LLAMA_MOE_CPU_POLL": "0", "LLAMA_MOE_CPU_POLL_US": "50000"}),
]

# Le celle a 47 strati ereditano da E4, che ha gia' l'elenco giusto; lo si
# riscrive comunque, perche' un preset non deve dipendere da cio' che eredita.
STRATI = {"S1": STRATI_47, "S2": STRATI_47, "S3": STRATI_8, "S4": STRATI_8}


def main():
    scritti = []
    for cella, base, etichetta, descrizione, env in CELLE:
        d = json.loads((BANCO / ("preset_%s_p4.json" % base)).read_text(encoding="utf-8"))
        d["id"] = cella + "_p7"
        d["etichetta"] = etichetta
        d["descrizione"] = descrizione
        d["fase"] = "P7-cella4"
        if cella in STRATI:
            d["env"]["LLAMA_MOE_CPU_LAYERS"] = STRATI[cella]
        # Le due opzioni nuove sono dichiarate SEMPRE, anche nello spento.
        d["env"].setdefault("LLAMA_MOE_CPU_POLL", "0")
        d["env"].setdefault("LLAMA_MOE_CPU_POLL_US", "50000")
        d["env"].update(env)
        d["differenze_dal_lato_B"] = "cella %s di P7-cella4: %s" % (cella, descrizione)
        out = BANCO / ("preset_%s_p7.json" % cella)
        out.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        scritti.append(out.name)
    for n in scritti:
        print("scritto", n)


if __name__ == "__main__":
    main()
