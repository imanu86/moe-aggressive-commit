# P7 cella 5 - genera i preset T1..T7 a partire da preset_S11_p7.json.
#
# Ogni preset dichiara TUTTE le opzioni dell'ibrido, comprese le due nuove della
# cella 5 (`LLAMA_MOE_CPU_PROBE`, `LLAMA_MOE_CPU_MTP_GUARD`): una corsa misurata
# con la configurazione sbagliata e' peggio di una corsa non misurata.
#
# JSON senza BOM, indentazione 1, come i preset esistenti.
import io, json, os, collections

QUI = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.abspath(os.path.join(QUI, "..", "banco_p0"))
BASE = os.path.join(BANCO, "preset_S11_p7.json")

with io.open(BASE, "r", encoding="utf-8") as f:
    base = json.load(f, object_pairs_hook=collections.OrderedDict)

CELLE = [
    ("T1", "p7c5_t1_mtp1_corsia_diagnostica_per_riga",
     "DIAGNOSI DI A7, passo 1 (profilo fumo). NON e' una misura di tempo. Modalita DIAGNOSTICA con la "
     "corsia di bozza accesa: il piano resta identico a cpu_max=0, il pool calcola gli esperti di sola "
     "bozza e la guardia confronta il contributo CPU con quello che la GPU calcola per le STESSE route, "
     "separando l'errore RIGA PER RIGA. Guardia del contesto di bozza SPENTA di proposito, per "
     "riprodurre lo stato della cella 4 e contare quante volte il contesto della BOZZA costruirebbe il "
     "nodo add. Le impronte devono restare identiche a M1/S6: in diagnostica y viene azzerato.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "1",
      "LLAMA_MOE_CPU_REPORT": "64", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "0", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T1B", "p7c5_t1b_mtp1_corsia_diagnostica_per_riga_guardia_accesa",
     "DIAGNOSI DI A7, passo 1 RIFATTO (profilo fumo). NON e' una misura di tempo. Identica a T1 ma con "
     "la GUARDIA DEL CONTESTO DI BOZZA ACCESA. T1 (guardia spenta) NON arriva in fondo al caricamento: "
     "il server muore con 'CUDA error: unspecified launch failure' subito dopo la creazione del "
     "contesto di bozza, perche' il grafo della BOZZA porta il nodo add del contributo CPU e la guardia "
     "del merge lo esegue in modalita' diagnostica leggendo il piano dell'ULTIMO strato del BERSAGLIO "
     "con i tensori della BOZZA: e' un accesso fuori dai limiti. Con la guardia accesa il nodo nel "
     "contesto di bozza non si costruisce, e il contatore g_draft_ctx_hits dice quante volte si sarebbe "
     "costruito. Da qui si leggono NRMSE e route CPU RIGA PER RIGA sul batch di verifica del bersaglio.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "1",
      "LLAMA_MOE_CPU_REPORT": "64", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T8", "p7c5_t8_mtp1_corsia_corretta_sonda_zero",
     "LA PROVA CHE NON PUO' MENTIRE, sul binario CORRETTO (profilo fumo). Identica a T6 (corsia accesa, "
     "guardia del contesto di bozza ACCESA) ma con la SONDA 1: la guardia del merge azzera y su TUTTE "
     "le righe dopo l'attesa e prima dell'add. Piano, maschera dei pesi e byte non trasferiti restano "
     "quelli della corsia vera: cambia SOLO il contributo che l'add somma. Se le impronte coincidono "
     "con T6, quell'add non arriva a moe_out; se differiscono, ci arriva.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "1", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T9", "p7c5_t9_mtp1_corsia_corretta_senza_aritmetica",
     "SCOMPOSIZIONE DI R (profilo fumo). Identica a T6 ma con LLAMA_MOE_CPU_NOCOMPUTE=1: il job viene "
     "pubblicato, accettato e validato, ma il pool non esegue una sola moltiplicazione e scrive zero. "
     "Separa il costo della CONSEGNA (impianto, attesa esposta, trasferimenti residui) da quello "
     "dell'ARITMETICA CPU. E' la cella S10 rifatta sul binario corretto: qui il confronto con T6 e' "
     "leggibile, perche' in cella 4 S7 e S10 erano identici solo perche' NESSUNO dei due sommava nulla.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "300000",
      "LLAMA_MOE_CPU_NOCOMPUTE": "1"}),

    ("T2", "p7c5_t2_mtp1_corsia_accesa_sonda_spenta",
     "DIAGNOSI DI A7, passo 2 (profilo fumo). E' S11 rifatto sul binario della cella 5, a strumentazione "
     "presente ma inerte: corsia di bozza accesa, sonda SPENTA, guardia del contesto di bozza SPENTA. "
     "Da' il riferimento del candidato (R, t/s, accettazione, impronte) contro cui si leggono le due "
     "sonde T3 e T4.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "0", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T3", "p7c5_t3_mtp1_corsia_accesa_sonda_zero",
     "DIAGNOSI DI A7, passo 3 (profilo fumo). Identico a T2 ma con la SONDA 1: la guardia del merge "
     "azzera y su TUTTE le righe dopo l'attesa e prima dell'add. Il piano, la maschera dei pesi e i "
     "byte non trasferiti restano quelli della corsia vera: cambia SOLO il contributo che l'add somma. "
     "Se le impronte coincidono con T2, il contributo CPU non arriva a moe_out. Contatori accesi: "
     "questa corsa da' anche le route CPU riga per riga in modo ATTIVO.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "64", "LLAMA_MOE_CPU_PROBE": "1", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "0", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T4", "p7c5_t4_mtp1_corsia_accesa_sonda_marcatore",
     "DIAGNOSI DI A7, passo 4 (profilo fumo). La prova che non puo' mentire: SONDA 4, y sostituito da "
     "un marcatore costante (1.0) su tutte le righe. Se l'add arriva a moe_out il testo deve cambiare "
     "in modo grossolano; se le impronte restano quelle di T2, quell'add non arriva. Non e' una misura "
     "di tempo ne' di qualita': e' un interruttore.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "4", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "0", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T5", "p7c5_t5_mtp1_corsia_spenta_riferimento",
     "RIFERIMENTO della cella 5 (profilo fumo): come S12, corsia spenta, sullo stesso binario di T1-T4. "
     "Serve a due cose: la neutralita' del binario (impronte identiche a M1/S6/S12) e il ciclo da cui "
     "si ricava R per differenza.",
     {"LLAMA_MOE_CPU": "0", "LLAMA_MOE_CPU_DRAFT_ROWS": "0", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "50000"}),

    ("T6", "p7c5_t6_mtp1_corsia_accesa_corretta",
     "CANDIDATO della cella 5 (profilo fumo): corsia di bozza accesa con la CORREZIONE di A7 e con la "
     "guardia del contesto di bozza ACCESA. Stessa configurazione di T2 per tutto il resto. E' la "
     "corsa da cui si legge R = ciclo - T1 - testa, con il cancello R < 13 ms.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "0", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "300000"}),

    ("T7", "p7c5_t7_mtp1_corsia_accesa_corretta_contatori",
     "Come T6 ma con i CONTATORI accesi: non e' una misura di tempo (i contatori forzano una "
     "sincronizzazione del dispositivo), e' la lettura dei byte risparmiati, delle route CPU riga per "
     "riga e degli invarianti dopo la correzione.",
     {"LLAMA_MOE_CPU": "1", "LLAMA_MOE_CPU_DRAFT_ROWS": "1", "LLAMA_MOE_CPU_DIAG": "0",
      "LLAMA_MOE_CPU_REPORT": "64", "LLAMA_MOE_CPU_PROBE": "0", "LLAMA_MOE_CPU_PROBE_VALUE": "1.0",
      "LLAMA_MOE_CPU_MTP_GUARD": "1", "LLAMA_MOE_CPU_POLL_US": "300000"}),
]

for ident, etichetta, descrizione, env in CELLE:
    p = json.loads(json.dumps(base), object_pairs_hook=collections.OrderedDict)
    p["id"] = ident + "_p7"
    p["etichetta"] = etichetta
    p["descrizione"] = descrizione
    p["fase"] = "P7-cella5"
    for k, v in env.items():
        p["env"][k] = v
    p["differenze_dal_lato_B"] = "cella " + ident + " di P7-cella5: " + descrizione
    dest = os.path.join(BANCO, "preset_" + ident + "_p7.json")
    testo = json.dumps(p, ensure_ascii=False, indent=1)
    with io.open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(testo + "\n")
    print("scritto", dest)
