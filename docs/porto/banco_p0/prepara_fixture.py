"""P0 — materializza UNA VOLTA le fixture del banco (nessun server richiesto).

Perche' esiste: il banco precedente costruiva il contesto lungo leggendo i sorgenti
al momento della corsa. I sorgenti cambieranno durante l'integrazione CPU/GPU, quindi
quei prompt non sono confrontabili fra due giorni diversi. Qui il riempimento viene
generato UNA SOLA VOLTA dai sorgenti di oggi e salvato su disco.

Idempotente per costruzione: se `filler_sorgenti_20260914.txt` esiste, NON viene
rigenerato (viene solo riverificato l'hash). Per rifare le fixture da zero si crea
una cartella con un'altra data, non si sovrascrive questa.

Dopo questo script serve `sigilla_fixture.py`, che con un server vivo aggiunge gli ID
token, i conteggi esatti e `fixtures_manifest.json`.
"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
SRC = Path(r"C:\Users\imanu\Documents\Codex\2026-09-09\c-users-imanu-source-repos-moe\work\qwen38_clean\source")
MOE_DEMAND = SRC / "ggml" / "src" / "ggml-cuda" / "moe-demand.cuh"

DATA = "20260914"
FILLER = FIX / f"filler_sorgenti_{DATA}.txt"
CODICE_COPIA = FIX / f"moe-demand_{DATA}.cuh"
# Abbondante di proposito: il taglio esatto a 32k/131k token lo fa sigilla_fixture.py.
FILLER_CHAR_MAX = 900_000


def sha(testo):
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- filler
def costruisci_filler():
    """Stessa ricetta del banco precedente (banco_http.py / prova_reale.py), congelata.

    Ordine deterministico: percorso relativo in forma posix, ordinato. Estensioni di
    codice, niente `build/`, niente file oltre 400 000 byte.
    """
    ammesse = (".cpp", ".c", ".h", ".cu", ".cuh", ".py")
    file = [p for p in SRC.rglob("*")
            if p.is_file() and p.suffix in ammesse
            and "build" not in p.parts and p.stat().st_size < 400_000]
    file.sort(key=lambda p: p.relative_to(SRC).as_posix())
    parti, n, usati = [], 0, []
    for p in file:
        t = p.read_text(encoding="utf-8", errors="replace")
        blocco = f"// ===== FILE {p.relative_to(SRC).as_posix()} =====\n{t}"
        parti.append(blocco)
        usati.append(p.relative_to(SRC).as_posix())
        n += len(blocco) + 1
        if n > FILLER_CHAR_MAX:
            break
    return "\n".join(parti), usati


# --------------------------------------------------------------------------- casi
ISTRUZIONE_CONTESTO = ('Leggi con attenzione il materiale seguente e rispondi soltanto "pronto".\n\n')

# Difetto trovato dalla corsa di fumo del 14/9: il modello ragiona in inglese e legge
# "1,888 MiB" come 1888 (virgola = separatore delle migliaia), sbagliando il conto per un
# motivo che non c'entra nulla con cio' che il banco deve misurare. Senza questa nota il
# caso sarebbe rumore sistematico in ogni confronto di qualita'. Si premette ai casi che
# contengono numeri decimali all'italiana.
NOTA_DECIMALI = ("Avvertenza di notazione: in questo problema la virgola e' il separatore "
                 "DECIMALE all'italiana. 1,888 vale poco meno di due, NON "
                 "milleottocentottantotto; 906,24 vale poco piu' di novecento.\n\n")
CASI_CON_DECIMALI = {"L04", "L05", "S01", "S05", "S07", "S08"}

LIBERI = [
    dict(id="L01", sottotipo="prosa", prompt=(
        "Spiega in italiano, per un collega che conosce il C++ ma non i modelli MoE, perche' il "
        "decode di un Mixture-of-Experts con pochi esperti residenti in VRAM puo' essere limitato "
        "dalla banda del bus PCIe invece che dal calcolo. Usa esempi numerici inventati da te per "
        "mostrare il conto dei byte per token, e chiudi elencando tre misure che distinguono un "
        "collo di bottiglia di banda da uno di calcolo."),
        rubrica=[
            "distingue byte/token trasferiti da FLOP eseguiti",
            "mostra almeno un conto numerico esplicito con le unita' indicate",
            "elenca tre misure distinte e dice cosa ciascuna falsificherebbe",
            "non afferma che il calcolo e' sempre il collo di bottiglia",
            "risposta in italiano, senza domande di chiarimento",
        ]),
    dict(id="L02", sottotipo="prosa", prompt=(
        "Spiega la differenza fra una politica di sfratto a frequenza decaduta (LFU con "
        "decadimento per epoche) e una LRU pura per una cache di esperti su GPU. Indica un "
        "carico in cui la prima vince chiaramente e uno in cui perde, spiegando il meccanismo e "
        "non solo il risultato. Concludi con il modo piu' economico di misurare quale delle due "
        "conviene su un carico dato."),
        rubrica=[
            "definisce correttamente entrambe le politiche",
            "il carico in cui LFU-decaduta vince e' descritto con un meccanismo, non solo asserito",
            "descrive anche un carico in cui perde",
            "propone una misura eseguibile e non un'opinione",
            "risposta in italiano",
        ]),
    dict(id="L03", sottotipo="spiegazione", prompt=(
        "Un collega sostiene che la decodifica speculativa 'sporca la cache' e quindi aumenta il "
        "traffico verso la GPU. Scrivi una spiegazione ragionata, con un modello di costo "
        "esplicito, di come la speculazione possa invece RIDURRE i byte per token accettato, e "
        "di quali condizioni servono perche' cio' accada. Indica anche il caso in cui il collega "
        "avrebbe ragione."),
        rubrica=[
            "introduce un modello di costo con byte per riga di verifica e token accettati per ciclo",
            "spiega l'ammortamento degli stessi esperti su piu' token accettati",
            "indica esplicitamente le condizioni (accettazione, unici per riga) che servono",
            "indica un caso in cui la speculazione peggiora il traffico",
            "risposta in italiano",
        ]),
    dict(id="L04", sottotipo="ragionamento", prompt=(
        "Risolvi mostrando i passaggi e poi dando la risposta finale su una riga a parte nella "
        "forma 'RISPOSTA: <numero> MiB'.\n\n"
        "Un modello ha 48 strati. Per ogni token, ogni strato richiede esattamente 10 esperti, e "
        "ogni esperto pesa 1,888 MiB. Una cache soddisfa il 41% delle richieste senza alcun "
        "trasferimento; il resto viene trasferito per intero. Quanti MiB vengono trasferiti per "
        "un singolo token? Arrotonda a un decimale."),
        atteso=dict(tipo="numero", valore=534.7, tolleranza=0.3,
                    regex=r"RISPOSTA:\s*([0-9]+[.,][0-9]+)\s*MiB"),
        rubrica=[
            "calcola 48 x 10 x 1,888 = 906,24 MiB di richiesta lorda",
            "applica il 59% e ottiene 534,7 MiB (tolleranza 0,3)",
            "la riga finale ha il formato richiesto",
        ]),
    dict(id="L05", sottotipo="ragionamento", prompt=(
        "Risolvi mostrando la tabella dei passaggi e poi dando la risposta finale su una riga a "
        "parte nella forma 'RISPOSTA: n=<numero>'.\n\n"
        "Un ciclo di verifica speculativa costa 38,9 ms fissi piu' 13,8 ms per ogni riga di bozza "
        "verificata. Con n righe di bozza, i token accettati attesi per ciclo valgono "
        "1 + somma per k da 1 a n di 0,753^k. Calcola, per n = 1, 2, 3 e 4, i token accettati "
        "attesi e i millisecondi per token accettato, e indica quale n minimizza i millisecondi "
        "per token accettato."),
        atteso=dict(tipo="intero", valore=2, regex=r"RISPOSTA:\s*n\s*=\s*([0-9]+)"),
        rubrica=[
            "calcola i quattro valori di token accettati (circa 1,753 / 2,320 / 2,747 / 3,069)",
            "calcola i ms per token accettato (circa 30,1 / 28,7 / 29,2 / 30,7)",
            "conclude n = 2",
            "la riga finale ha il formato richiesto",
        ]),
    dict(id="L06", sottotipo="codice", prompt=(
        "Scrivi codice C++17 completo e autonomo (un solo file, con `int main()`), senza "
        "dipendenze esterne oltre la libreria standard.\n\n"
        "Implementa una classe `CacheFrequenzaDecaduta` con capacita' fissa passata al "
        "costruttore. L'interfaccia minima e':\n"
        "  bool accedi(int id);            // true se era presente (colpo), false se inserito ora\n"
        "  std::vector<int> residenti() const;  // gli id presenti, in ordine crescente\n"
        "  long long colpi() const; long long mancanze() const;\n\n"
        "Regole: ogni accesso incrementa un contatore di frequenza dell'id e ne aggiorna "
        "l'istante d'uso. Ogni 64 accessi l'epoca avanza e tutte le frequenze vengono dimezzate "
        "(divisione intera). Quando la cache e' piena, la vittima e' l'elemento con frequenza "
        "minima; a pari frequenza il meno recente; a pari recenza l'id minore.\n\n"
        "Aggiungi nel `main()` almeno cinque test con `assert` che coprano: inserimento e colpo, "
        "sfratto a capacita' piena, effetto del dimezzamento dopo 64 accessi, pareggio risolto "
        "dalla recenza e pareggio risolto dall'id minore. Stampa 'OK' alla fine."),
        rubrica=[
            "un solo file compilabile, include corretti, nessuna dipendenza esterna",
            "presenti tutti e quattro i metodi richiesti con le firme indicate",
            "lo sfratto usa frequenza, poi recenza, poi id minore",
            "il dimezzamento avviene a epoche di 64 accessi",
            "almeno cinque assert che coprono i cinque casi elencati, e la stampa finale OK",
        ]),
    dict(id="L07", sottotipo="codice", prompt=(
        "Scrivi un modulo Python autonomo (un solo file, solo libreria standard) che espone:\n\n"
        "  def throughput_insieme(casi: list[dict]) -> float\n\n"
        "dove ogni caso e' un dizionario con le chiavi 'token_accettati' (int) e "
        "'tempo_generazione_s' (float). La funzione deve restituire "
        "somma(token_accettati) / somma(tempo_generazione_s), cioe' NON la media aritmetica dei "
        "token al secondo dei singoli casi. Deve sollevare `ValueError` se la lista e' vuota, se "
        "un tempo e' negativo o se la somma dei tempi e' zero, e deve ignorare i casi marcati "
        "con 'valido': False.\n\n"
        "Aggiungi nello stesso file una suite di test eseguibile con `python il_file.py` (usando "
        "`unittest`) che dimostri con un caso numerico esplicito che il risultato differisce "
        "dalla media aritmetica dei t/s per caso, piu' i test degli errori e dell'esclusione dei "
        "casi non validi."),
        rubrica=[
            "la funzione calcola somma/somma e non la media dei rapporti",
            "solleva ValueError nei tre casi richiesti",
            "ignora i casi con 'valido': False",
            "i test sono eseguibili con python il_file.py e usano unittest",
            "un test mostra numericamente la differenza dalla media aritmetica",
        ]),
    dict(id="L08", sottotipo="codice", prompt=(
        "Scrivi codice C++17 completo e autonomo (un solo file con `int main()`, solo libreria "
        "standard).\n\n"
        "Implementa:\n"
        "  struct Piano { std::vector<int> colpi; std::vector<int> mancanze_gpu; "
        "std::vector<int> mancanze_cpu; };\n"
        "  Piano pianifica(const std::vector<int>& richiesti,\n"
        "                  const std::vector<int>& residenti,\n"
        "                  int max_cpu);\n\n"
        "`richiesti` puo' contenere duplicati: il piano lavora sugli id UNICI, conservando il "
        "primo ordine di comparsa. Gli id presenti fra i `residenti` vanno in `colpi`. I "
        "mancanti vanno in `mancanze_cpu` fino a `max_cpu` elementi (nell'ordine di comparsa) e "
        "i restanti in `mancanze_gpu`. Deve valere sempre l'invariante "
        "`colpi.size() + mancanze_gpu.size() + mancanze_cpu.size() == numero di id unici`.\n\n"
        "Aggiungi nel `main()` almeno sei test con `assert`: nessun mancante, tutti mancanti, "
        "duplicati nei richiesti, max_cpu = 0, max_cpu maggiore del numero di mancanti, e la "
        "verifica esplicita dell'invariante su un caso misto. Stampa 'OK' alla fine."),
        rubrica=[
            "deduplica conservando il primo ordine di comparsa",
            "il partizionamento rispetta max_cpu e l'ordine",
            "l'invariante e' verificato da un assert esplicito",
            "almeno sei test che coprono i sei casi elencati",
            "un solo file compilabile, stampa finale OK",
        ]),
]

# --- qualita' strutturata aggiuntiva (oltre agli otto liberi e ai cinque fatti lunghi) ---
TABELLA_S05 = (
    "| configurazione | slot | t/s | MB per token |\n"
    "|---|---|---|---|\n"
    "| base      | 0  | 14,71 | 190 |\n"
    "| meta'     | 32 | 22,18 | 742 |\n"
    "| piena     | 64 | 24,64 | 562 |\n"
)

SNIPPET_S06 = (
    "int scegli_vittima(const std::vector<int>& freq, const std::vector<int>& ultimo_uso,\n"
    "                   const std::vector<bool>& usato_ora) {\n"
    "    int migliore = -1;\n"
    "    for (int i = 0; i < (int) freq.size(); ++i) {\n"
    "        if (usato_ora[i]) continue;\n"
    "        if (migliore < 0) { migliore = i; continue; }\n"
    "        if (freq[i] < freq[migliore]) migliore = i;\n"
    "        else if (freq[i] == freq[migliore] && ultimo_uso[i] > ultimo_uso[migliore]) migliore = i;\n"
    "    }\n"
    "    return migliore;\n"
    "}\n"
)

QUALITA = [
    dict(id="S01", sottotipo="json", prompt=(
        "Rispondi esclusivamente con un oggetto JSON valido, senza testo prima o dopo e senza "
        "blocchi di codice. Chiavi esatte e obbligatorie: \"strati\" (intero), "
        "\"esperti_attivi\" (intero), \"mib_per_esperto\" (numero), "
        "\"mib_per_token_lordi\" (numero). Usa questi dati: 48 strati, 10 esperti attivi per "
        "strato, 1,888 MiB per esperto. L'ultimo campo e' il prodotto dei tre precedenti."),
        atteso=dict(tipo="json", chiavi=["strati", "esperti_attivi", "mib_per_esperto",
                                         "mib_per_token_lordi"],
                    valori={"strati": 48, "esperti_attivi": 10, "mib_per_esperto": 1.888,
                            "mib_per_token_lordi": 906.24},
                    tolleranza=0.05),
        rubrica=["JSON valido e nient'altro nella risposta",
                 "esattamente le quattro chiavi richieste",
                 "mib_per_token_lordi = 906,24 entro 0,05"]),
    dict(id="S02", sottotipo="json", prompt=(
        "Rispondi esclusivamente con un oggetto JSON valido, senza testo prima o dopo. Deve "
        "avere la chiave \"ripartizione\" con un oggetto di tre chiavi: \"trasferimento\", "
        "\"calcolo\", \"coordinamento\". I tre valori sono percentuali interi e la loro somma "
        "deve essere esattamente 100. Assegna la quota maggiore al trasferimento."),
        atteso=dict(tipo="json_vincolo", vincolo="somma_100_trasferimento_max"),
        rubrica=["JSON valido e nient'altro", "tre chiavi esatte",
                 "somma esattamente 100", "trasferimento e' il valore maggiore"]),
    dict(id="S03", sottotipo="formato", prompt=(
        "Elenca cinque controlli da fare prima di lanciare un benchmark su questa macchina. "
        "Vincoli rigidi: esattamente cinque righe, ogni riga inizia con '- ', ogni riga contiene "
        "al massimo otto parole, nessun titolo, nessuna riga vuota, nessun testo oltre le cinque "
        "righe."),
        atteso=dict(tipo="formato", righe=5, prefisso="- ", max_parole_riga=8),
        rubrica=["esattamente cinque righe", "ogni riga inizia con '- '",
                 "nessuna riga oltre otto parole", "nessun testo aggiuntivo"]),
    dict(id="S04", sottotipo="formato", prompt=(
        "Un server di inferenza e' in ascolto sulla porta 8100 e ne viene avviato un secondo con "
        "la stessa porta e lo stesso modello da 76 GiB, su una macchina con 96 GB di RAM. "
        "Rispondi con UNA SOLA PAROLA, in minuscolo, senza punteggiatura: la parola deve essere "
        "'impossibile' se i due processi non possono coesistere, 'possibile' se possono."),
        atteso=dict(tipo="esatto", valore="impossibile"),
        rubrica=["una sola parola", "la parola e' 'impossibile'"]),
    dict(id="S05", sottotipo="recupero", prompt=(
        "Dalla tabella seguente ricava la risposta.\n\n" + TABELLA_S05 +
        "\nDi quanti punti percentuali aumenta il throughput passando da 32 a 64 slot, e di "
        "quanto per cento scendono i MB per token nello stesso passaggio? Mostra i due conti e "
        "chiudi con una riga nella forma 'RISPOSTA: +<x>% t/s, -<y>% MB/token' con un decimale."),
        atteso=dict(tipo="due_numeri",
                    regex=r"RISPOSTA:\s*\+?([0-9]+[.,][0-9]+)%\s*t/s,\s*-?([0-9]+[.,][0-9]+)%",
                    valori=[11.1, 24.3], tolleranza=0.4),
        rubrica=["usa 22,18 e 24,64 per il throughput (+11,1%)",
                 "usa 742 e 562 per i byte (-24,3%)",
                 "la riga finale ha il formato richiesto"]),
    dict(id="S06", sottotipo="codice", prompt=(
        "La funzione seguente deve scegliere come vittima l'elemento con frequenza minima; a "
        "pari frequenza il MENO recente (cioe' quello con `ultimo_uso` piu' piccolo); a pari "
        "recenza l'indice minore. Contiene un difetto. Individualo, spiegalo in una frase e "
        "restituisci la funzione corretta.\n\n```cpp\n" + SNIPPET_S06 + "```"),
        atteso=dict(tipo="contiene_uno", alternative=["ultimo_uso[i] < ultimo_uso[migliore]",
                                                      "ultimo_uso[i] <ultimo_uso[migliore]"]),
        rubrica=["individua il confronto di recenza invertito (> invece di <)",
                 "la funzione corretta usa < sul confronto di ultimo_uso",
                 "gestisce anche il pareggio sull'indice minore senza cambiarne il senso",
                 "non introduce altre modifiche di comportamento"]),
    dict(id="S07", sottotipo="numerico", prompt=(
        "Converti e mostra i passaggi. Un bus trasferisce 562 MiB per ogni token generato e il "
        "modello genera 24,64 token al secondo. Quanti GB al secondo (base 10, cioe' "
        "1 GB = 10^9 byte) transitano sul bus? Chiudi con una riga nella forma "
        "'RISPOSTA: <numero> GB/s' con due decimali."),
        atteso=dict(tipo="numero", valore=14.52, tolleranza=0.20,
                    regex=r"RISPOSTA:\s*([0-9]+[.,][0-9]+)\s*GB/s"),
        rubrica=["converte MiB in byte con 1 MiB = 1048576 byte",
                 "moltiplica per 24,64 token al secondo",
                 "risultato circa 14,5 GB/s (tolleranza 0,2)",
                 "la riga finale ha il formato richiesto"]),
    dict(id="S08", sottotipo="ragionamento", prompt=(
        "Tre assetti sono stati misurati sulla stessa sequenza: A = 249,78 token al secondo di "
        "prefill, B = 294,95, C = 251,02. Il rumore ripetuto della misura e' +/-0,2%. Quali "
        "differenze sono distinguibili dal rumore e quali no? Mostra il conto di ciascun "
        "confronto e chiudi con una riga 'RISPOSTA: <elenco delle coppie distinguibili>'."),
        atteso=dict(tipo="giudizio",
                    deve_contenere=["A", "B", "C"],
                    nota="A-B e B-C distinguibili; A-C (+0,50%) sopra il rumore ma dello stesso "
                         "ordine: la risposta deve trattarla come piccola e discutere il margine"),
        rubrica=["calcola le tre differenze percentuali (+18,1%, -17,4%, +0,50%)",
                 "conclude che A-B e B-C sono ampiamente distinguibili",
                 "tratta A-C come marginale e ne discute il confronto col rumore dichiarato",
                 "non dichiara distinguibile una differenza sotto lo 0,2%"]),
    dict(id="S09", sottotipo="onesta", prompt=(
        "Nel testo seguente, e solo in esso, cerca il numero di serie del banco OMEGA.\n\n"
        "NOTA OPERATIVA ALFA: il codice di collaudo del banco ALFA e' MANDORLA-417.\n"
        "NOTA OPERATIVA BETA: il colore di segnalazione del banco BETA e' VIOLA-CENERE.\n\n"
        "Se il dato non c'e', dillo esplicitamente e non inventarlo. Rispondi in una sola frase."),
        atteso=dict(tipo="negativo", vietati=["OMEGA-", "ZR-", "MANDORLA-417 e' il numero"],
                    deve_negare=True),
        rubrica=["dichiara che il dato non e' presente",
                 "non inventa un numero di serie",
                 "una sola frase"]),
    dict(id="S10", sottotipo="vincolo", prompt=(
        "Traduci in italiano la frase seguente lasciando invariati, esattamente come sono "
        "scritti, i tre termini `prompt cache`, `flash attention` e `MoE expert cache`. Non "
        "aggiungere commenti.\n\n"
        "\"When the prompt cache is disabled, flash attention still runs, but the MoE expert "
        "cache must be refilled from host memory at every step.\""),
        atteso=dict(tipo="contiene_tutti",
                    termini=["prompt cache", "flash attention", "MoE expert cache"]),
        rubrica=["i tre termini compaiono invariati",
                 "la frase e' tradotta in italiano e mantiene il senso",
                 "nessun commento aggiuntivo"]),
]

# --- cinque fatti a contesto lungo, identici a prova_reale.py (v2 corretta il 13/9) ---
AGHI = [
    (0.05, "NOTA OPERATIVA ALFA: il codice di collaudo del banco ALFA e' MANDORLA-417.",
     "Qual e' il codice di collaudo del banco ALFA? Rispondi con il solo codice.", "MANDORLA-417"),
    (0.25, "NOTA OPERATIVA BETA: il colore di segnalazione del banco BETA e' VIOLA-CENERE.",
     "Qual e' il colore di segnalazione del banco BETA? Rispondi con la sola parola.", "VIOLA-CENERE"),
    (0.50, "NOTA OPERATIVA GAMMA: il responsabile del banco GAMMA e' Ferruccio Malinverni.",
     "Chi e' il responsabile del banco GAMMA? Rispondi con il solo cognome.", "Malinverni"),
    (0.75, "NOTA OPERATIVA DELTA: il numero di serie del banco DELTA e' ZR-8842.",
     "Qual e' il numero di serie del banco DELTA? Rispondi con il solo numero.", "ZR-8842"),
    (0.95, "NOTA OPERATIVA EPSILON: la parola d'ordine del banco EPSILON e' TRAMONTANA.",
     "Qual e' la parola d'ordine del banco EPSILON? Rispondi con la sola parola.", "TRAMONTANA"),
]

DOMANDA_TECNICA = (
    "Nel codice che ti ho dato c'e' il file common/arg.cpp con la definizione delle opzioni "
    "da riga di comando. Quale opzione regola il numero di slot della cache degli esperti MoE "
    "sulla GPU, qual e' il suo valore predefinito, e quale opzione imparentata limita gli "
    "inserimenti per strato a ogni passo di decode? Rispondi in italiano citando i nomi esatti."
)

PROMPT_PREFILL = 'Hai letto il materiale. Rispondi soltanto con la parola: pronto.'


def testo_prompt(c):
    """Premette l'avvertenza di notazione ai soli casi con decimali all'italiana."""
    if c["id"] in CASI_CON_DECIMALI:
        return NOTA_DECIMALI + c["prompt"]
    return c["prompt"]


def costruisci_casi():
    casi = []
    for c in LIBERI:
        casi.append(dict(
            id=c["id"], insiemi=["libero", "qualita"], sottotipo=c["sottotipo"],
            contesti=["corto", "ctx32k"], prefisso_per_contesto={"corto": None, "ctx32k": "ctx32k"},
            # 512 token NON bastano al gruppo libero con --reasoning on: nella corsa di
            # fumo del 14/9 L01 ha consumato tutti i 512 dentro il ragionamento e ha
            # prodotto ZERO testo finale. Il protocollo dice che un output troncato nel
            # solo ragionamento non supera la qualita': in screening servono 1024.
            budget_token={"screening": 1024, "conferma": 1536},
            prompt=testo_prompt(c), atteso=c.get("atteso"), rubrica=c["rubrica"],
        ))
    for c in QUALITA:
        casi.append(dict(
            id=c["id"], insiemi=["qualita"], sottotipo=c["sottotipo"],
            contesti=["corto"], prefisso_per_contesto={"corto": None},
            budget_token={"screening": 768, "conferma": 768},
            prompt=testo_prompt(c), atteso=c.get("atteso"), rubrica=c["rubrica"],
        ))
    for frazione, _, domanda, atteso in AGHI:
        casi.append(dict(
            id="Q_AGO_%02d" % int(frazione * 100), insiemi=["qualita"], sottotipo="ago_contesto_lungo",
            contesti=["aghi131k"], prefisso_per_contesto={"aghi131k": "aghi131k"},
            budget_token={"screening": 768, "conferma": 768},
            profondita_ago=frazione, prompt=domanda,
            atteso=dict(tipo="contiene", valore=atteso),
            rubrica=["la stringa attesa compare nella risposta finale",
                     "la risposta non e' troncata dentro il ragionamento"],
        ))
    casi.append(dict(
        id="Q_TEC", insiemi=["qualita"], sottotipo="tecnica_contesto_lungo",
        contesti=["aghi131k"], prefisso_per_contesto={"aghi131k": "aghi131k"},
        budget_token={"screening": 768, "conferma": 768}, prompt=DOMANDA_TECNICA,
        atteso=dict(tipo="contiene_tutti", termini=["--moe-expert-cache", "--moe-expert-cache-inserts"]),
        rubrica=["cita --moe-expert-cache con il valore predefinito",
                 "cita --moe-expert-cache-inserts come opzione imparentata",
                 "non inventa opzioni inesistenti"],
    ))
    for cid, prefisso in (("PF_32K", "ctx32k"), ("PF_131K", "ctx131k")):
        casi.append(dict(
            id=cid, insiemi=["prefill"], sottotipo="prefill_freddo",
            contesti=[prefisso], prefisso_per_contesto={prefisso: prefisso},
            budget_token={"screening": 64, "conferma": 64}, prompt=PROMPT_PREFILL,
            atteso=dict(tipo="contiene", valore="pronto"),
            rubrica=["risposta brevissima", "prompt_n vicino al bersaglio dichiarato"],
        ))
    for cid, lavoro in (("C01", "copia"), ("C02", "rinomina")):
        if lavoro == "copia":
            testo = ("Riscrivi INTEGRALMENTE il file seguente senza modificarlo, riga per riga. "
                     "Non aggiungere commenti, non spiegare nulla, restituisci soltanto il codice."
                     "\n\n```\n{CODICE}\n```")
        else:
            testo = ("Riscrivi INTEGRALMENTE il file seguente sostituendo ovunque "
                     "l'identificatore `bound_group` con `gruppo_legato`. Lascia tutto il resto "
                     "invariato, riga per riga. Non spiegare nulla, restituisci soltanto il "
                     "codice.\n\n```\n{CODICE}\n```")
        casi.append(dict(
            id=cid, insiemi=["copia"], sottotipo=lavoro, contesti=["corto"],
            prefisso_per_contesto={"corto": None},
            budget_token={"screening": 1024, "conferma": 1024},
            prompt_template=testo, codice_sorgente=CODICE_COPIA.name,
            atteso=dict(tipo="frazione_righe_copiate", minimo=0.90,
                        trasformazione=None if lavoro == "copia" else ["bound_group", "gruppo_legato"]),
            rubrica=["frazione di righe identiche all'atteso almeno 0,90",
                     "nessun commento aggiunto",
                     "per la rinomina: nessuna occorrenza residua di bound_group"],
        ))
    return casi


def main():
    FIX.mkdir(parents=True, exist_ok=True)
    stato = {}

    if FILLER.exists():
        testo = FILLER.read_text(encoding="utf-8")
        elenco = json.loads((FIX / f"filler_file_usati_{DATA}.json").read_text(encoding="utf-8"))
        stato["filler"] = "RIUSATO (mai rigenerato)"
    else:
        testo, elenco = costruisci_filler()
        FILLER.write_text(testo, encoding="utf-8", newline="\n")
        (FIX / f"filler_file_usati_{DATA}.json").write_text(
            json.dumps(elenco, indent=1), encoding="utf-8")
        stato["filler"] = "GENERATO ORA dai sorgenti di oggi"
    print("filler: %s  %d caratteri, %d file, sha256=%s" %
          (stato["filler"], len(testo), len(elenco), sha(testo)[:16]))

    if not CODICE_COPIA.exists():
        shutil.copy2(MOE_DEMAND, CODICE_COPIA)
        print("congelato %s da %s" % (CODICE_COPIA.name, MOE_DEMAND))
    codice = CODICE_COPIA.read_text(encoding="utf-8", errors="replace")
    print("codice copia/rinomina: %d caratteri, sha256=%s" % (len(codice), sha(codice)[:16]))

    casi = costruisci_casi()
    (FIX / "casi.json").write_text(json.dumps(
        dict(versione=1, data=DATA, creato=datetime.now().isoformat(timespec="seconds"),
             istruzione_contesto=ISTRUZIONE_CONTESTO,
             filler=FILLER.name, filler_sha256=sha(testo), filler_caratteri=len(testo),
             codice_copia=CODICE_COPIA.name, codice_copia_sha256=sha(codice),
             aghi=[dict(profondita=f, testo=t, atteso=x) for f, t, _, x in AGHI],
             casi=casi), indent=1, ensure_ascii=False), encoding="utf-8")

    conta = {}
    for c in casi:
        for i in c["insiemi"]:
            conta[i] = conta.get(i, 0) + 1
    print("casi scritti: %d totali  %s" % (len(casi), conta))
    print("\nORA serve un server vivo: python sigilla_fixture.py")


if __name__ == "__main__":
    main()
