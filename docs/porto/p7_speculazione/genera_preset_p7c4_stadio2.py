"""P7, cella 4, stadio 2 — generatore dei preset S6/S7/S8/S9.

Base: `preset_M1_p7.json` (MTP bozza 1, riferimento 28,66 t/s) e
`preset_M2_p7.json` (bozza 2). Si cambiano DUE cose e si dichiara tutto il
resto:
  - `binari`, che passano da `qwen38_clean\\build\\bin` alla copia di lavoro
    `D:\\ds4_work\\p3_work\\build\\bin` (e' la prova di neutralita' dei binari,
    quindi il preset deve dirlo);
  - le variabili `LLAMA_MOE_CPU*`, dichiarate TUTTE e ESPLICITAMENTE, anche
    quelle che valgono il default.

  python genera_preset_p7c4_stadio2.py
"""
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"
BINARI = "D:\\ds4_work\\p3_work\\build\\bin"
STRATI_47 = ",".join(str(i) for i in range(48) if i != 2)

# Impianto a polling (stadio 1, cancello superato a 13,8 us/strato) + corsia di
# bozza. `LLAMA_MOE_CPU_MAX=0` di proposito: la riga 0 non devia NIENTE, cio' che
# va alla CPU lo decide la sola riga di bozza.
COMUNE = {
    "LLAMA_MOE_CPU_LAYERS": STRATI_47,
    "LLAMA_MOE_CPU_MAX": "0",
    "LLAMA_MOE_CPU_THREADS": "2",
    "LLAMA_MOE_CPU_REPORT": "0",
    "LLAMA_MOE_CPU_WAIT_US": "2000000",
    "LLAMA_MOE_CPU_ACK_US": "200000",
    "LLAMA_MOE_CPU_DIAG": "0",
    "LLAMA_MOE_CPU_ALLOW_ZERO": "0",
    "LLAMA_MOE_CPU_NODES": "31",
    "LLAMA_MOE_CPU_NOCOMPUTE": "0",
    "LLAMA_MOE_CPU_FUSE": "1",
    "LLAMA_MOE_CPU_FUSE_SPIN_US": "0",
    "LLAMA_MOE_CPU_GUARD_LIGHT": "1",
    "LLAMA_MOE_CPU_AFFINITY": "auto",
    "LLAMA_MOE_CPU_POLL": "1",
    "LLAMA_MOE_CPU_POLL_US": "50000",
}

CELLE = [
    ("S6", "M1", "p7c4_s6_mtp1_corsia_spenta",
     "PROVA 1 — NEUTRALITA' DEI BINARI. M1 (MTP bozza 1) sui binari della copia di lavoro, corsia di "
     "bozza SPENTA e ibrido SPENTO. Le impronte devono essere identiche a M1 e il t/s vicino a 28,66: "
     "se non lo sono, nessun confronto successivo e' attribuibile alla leva.",
     dict(COMUNE, **{"LLAMA_MOE_CPU": "0", "LLAMA_MOE_CPU_DRAFT_ROWS": "0"})),
    ("S7", "M1", "p7c4_s7_mtp1_corsia_accesa",
     "PROVA 2/3 — LA LEVA. M1 (MTP bozza 1) con la CORSIA CPU SULLE RIGHE DI BOZZA accesa su 47 strati: "
     "gli esperti non residenti chiesti solo dalla riga di bozza non si trasferiscono e non si ammettono. "
     "Impronte attese IDENTICHE a M1 (la corsia calcola la stessa FFN: iso-testo).",
     dict(COMUNE, **{"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1"})),
    ("S8", "M2", "p7c4_s8_mtp2_corsia_accesa",
     "PROVA 4 — BOZZA 2 con la corsia accesa. La cella 3 prevede che con R piu' basso la soglia di "
     "pareggio della seconda posizione scenda da 0,633 a ~0,501, sotto lo 0,553 misurato in cella 1.",
     dict(COMUNE, **{"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1"})),
    ("S9", "M1", "p7c4_s9_mtp1_corsia_accesa_contatori",
     "VERIFICA (profilo fumo), NON una misura di tempo: LLAMA_MOE_CPU_REPORT forza un "
     "cudaDeviceSynchronize. Serve a leggere invariante 1, esperti CPU per ciclo, byte risparmiati e "
     "valori non finiti con la corsia accesa.",
     dict(COMUNE, **{"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_REPORT": "64"})),
]


def main():
    for cella, base, etichetta, descrizione, env in CELLE:
        d = json.loads((BANCO / ("preset_%s_p7.json" % base)).read_text(encoding="utf-8"))
        d["id"] = cella + "_p7"
        d["etichetta"] = etichetta
        d["descrizione"] = descrizione
        d["fase"] = "P7-cella4"
        d["binari"] = BINARI
        d["env"].update(env)
        d["differenze_dal_lato_B"] = "cella %s di P7-cella4 (base %s): %s" % (cella, base, descrizione)
        note = d.setdefault("deviazioni_dal_lanciatore_quotidiano", [])
        note.append("binari della copia di lavoro D:\\ds4_work\\p3_work\\build\\bin invece di "
                    "qwen38_clean\\build\\bin: e' la copia patchata di P3/P4/P7-cella4. "
                    "qwen38_clean e bin_prod non sono stati toccati.")
        out = BANCO / ("preset_%s_p7.json" % cella)
        out.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("scritto", out.name)


if __name__ == "__main__":
    main()
