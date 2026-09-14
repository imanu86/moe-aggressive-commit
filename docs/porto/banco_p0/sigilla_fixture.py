"""P0 — sigilla le fixture: ID token, conteggi esatti, hash. Richiede un server VIVO.

Non esiste un `llama-tokenize.exe` compilato in questo albero (in `build\\tools\\tokenize`
c'e' solo la cartella di CMake), quindi gli ID token si ottengono dagli endpoint
`/tokenize` e `/detokenize` del server. E' dichiarato nel manifest: il vocabolario e'
quello del binario in esame, non di un tokenizzatore esterno.

Lo script e' idempotente: se `fixtures_manifest.json` esiste non lo riscrive, salvo
`--rifai`. Le fixture sono immutabili per costruzione: si conservano insieme testo,
ID token e hash, e i testi lunghi vengono derivati UNA VOLTA dal filler congelato.

Uso:  python sigilla_fixture.py [--url http://127.0.0.1:8100] [--rifai]
"""
import argparse
import gzip
import hashlib
import json
import re
import struct
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
PROMPTS = FIX / "prompts"
IDS = FIX / "ids"
BAT_PROD = Path(r"C:\Users\imanu\Desktop\avvia Qwen38 250k DeepSeek Harness.bat")

BERSAGLI = {"ctx32k": 32768, "ctx131k": 131072}
SOGLIA_IDS_BINARI = 4096


def chiave():
    """La API key viene letta localmente e non finisce in nessun file scritto."""
    return re.search(r'set "API_KEY=([^"]*)"', BAT_PROD.read_text(errors="replace")).group(1)


def sha_testo(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


class Cliente:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.h = {"Content-Type": "application/json; charset=utf-8",
                  "Authorization": "Bearer " + chiave()}

    def post(self, path, body, timeout=1800):
        dati = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=dati, headers=self.h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def tokenize(self, testo):
        return self.post("/tokenize", {"content": testo})["tokens"]

    def detokenize(self, tokens):
        return self.post("/detokenize", {"tokens": tokens})["content"]


def salva_ids(nome, tokens):
    """ID token su disco. Oltre 4096 token: int32 little-endian compresso con gzip.

    L'SHA256 registrato e' quello dei byte NON compressi, per essere indipendente
    dalla libreria di compressione.
    """
    IDS.mkdir(parents=True, exist_ok=True)
    grezzo = struct.pack("<%di" % len(tokens), *tokens)
    h = hashlib.sha256(grezzo).hexdigest()
    if len(tokens) > SOGLIA_IDS_BINARI:
        p = IDS / (nome + ".ids.bin.gz")
        with gzip.open(p, "wb", compresslevel=6) as f:
            f.write(grezzo)
        formato = "int32_le_gzip"
    else:
        p = IDS / (nome + ".ids.json")
        p.write_text(json.dumps(tokens), encoding="utf-8")
        formato = "json_lista_interi"
    return {"file": p.name, "formato": formato, "n_token": len(tokens),
            "sha256_byte_int32_le": h}


def prefisso_lungo(cl, nome, filler, bersaglio):
    """Taglia il filler congelato a esattamente `bersaglio` token e materializza il testo."""
    p = FIX / (nome + ".txt")
    if p.exists():
        testo = p.read_text(encoding="utf-8")
        tok = cl.tokenize(testo)
        return testo, tok, "RIUSATO"
    tok_tutti = cl.tokenize(filler)
    if len(tok_tutti) < bersaglio:
        raise SystemExit("filler troppo corto: %d token, ne servono %d" % (len(tok_tutti), bersaglio))
    testo = cl.detokenize(tok_tutti[:bersaglio])
    p.write_text(testo, encoding="utf-8", newline="\n")
    tok = cl.tokenize(testo)
    return testo, tok, "CREATO"


def contesto_aghi(cl, base_testo, aghi):
    """Stessa ricetta di prova_reale.py: gli aghi entrano a frazioni di CARATTERI."""
    p = FIX / "aghi131k.txt"
    if p.exists():
        testo = p.read_text(encoding="utf-8")
        return testo, cl.tokenize(testo), "RIUSATO"
    pezzi, ultimo = [], 0
    for a in aghi:
        taglio = int(len(base_testo) * a["profondita"])
        pezzi.append(base_testo[ultimo:taglio])
        pezzi.append("\n\n// %s\n\n" % a["testo"])
        ultimo = taglio
    pezzi.append(base_testo[ultimo:])
    testo = "".join(pezzi)
    p.write_text(testo, encoding="utf-8", newline="\n")
    return testo, cl.tokenize(testo), "CREATO"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8100")
    ap.add_argument("--rifai", action="store_true")
    args = ap.parse_args()

    man_path = FIX / "fixtures_manifest.json"
    if man_path.exists() and not args.rifai:
        print("fixtures_manifest.json esiste gia': niente da fare (usa --rifai per forzare)")
        return 0

    casi_doc = json.loads((FIX / "casi.json").read_text(encoding="utf-8"))
    filler = (FIX / casi_doc["filler"]).read_text(encoding="utf-8")
    codice = (FIX / casi_doc["codice_copia"]).read_text(encoding="utf-8")
    assert sha_testo(filler) == casi_doc["filler_sha256"], "il filler e' stato modificato!"
    assert sha_testo(codice) == casi_doc["codice_copia_sha256"], "il codice congelato e' cambiato!"

    cl = Cliente(args.url)
    t0 = time.time()
    prefissi = {}

    for nome, bersaglio in BERSAGLI.items():
        testo, tok, stato = prefisso_lungo(cl, nome, filler, bersaglio)
        prefissi[nome] = {
            "file": nome + ".txt", "stato": stato, "bersaglio_token": bersaglio,
            "caratteri": len(testo), "sha256_testo": sha_testo(testo),
            "n_token_riverificato": len(tok),
            "scarto_dal_bersaglio": len(tok) - bersaglio,
            "ids": salva_ids(nome, tok),
        }
        print("%s: %s  %d caratteri, %d token (scarto %+d)" %
              (nome, stato, len(testo), len(tok), len(tok) - bersaglio), flush=True)

    base = (FIX / "ctx131k.txt").read_text(encoding="utf-8")
    testo, tok, stato = contesto_aghi(cl, base, casi_doc["aghi"])
    prefissi["aghi131k"] = {
        "file": "aghi131k.txt", "stato": stato,
        "derivato_da": "ctx131k.txt piu' cinque note operative a frazioni di caratteri",
        "caratteri": len(testo), "sha256_testo": sha_testo(testo),
        "n_token_riverificato": len(tok), "ids": salva_ids("aghi131k", tok),
        "profondita_aghi": [a["profondita"] for a in casi_doc["aghi"]],
    }
    print("aghi131k: %s  %d caratteri, %d token" % (stato, len(testo), len(tok)), flush=True)

    for a in casi_doc["aghi"]:
        # se l'atteso esistesse gia' nel materiale, "trovato" non proverebbe nulla.
        # La v1 di questo controllo deduceva l'atteso con una regex e dava un falso
        # allarme su 'F' (da "Ferruccio"): ora l'atteso arriva dal catalogo dei casi.
        atteso = a.get("atteso")
        if atteso and atteso.lower() in base.lower():
            print("  ATTENZIONE: '%s' compare gia' nel materiale: ago inutilizzabile" % atteso)

    PROMPTS.mkdir(parents=True, exist_ok=True)
    casi_out = []
    for c in casi_doc["casi"]:
        testo_prompt = c.get("prompt")
        if testo_prompt is None:
            testo_prompt = c["prompt_template"].replace("{CODICE}", codice)
        pfile = PROMPTS / ("%s.txt" % c["id"])
        pfile.write_text(testo_prompt, encoding="utf-8", newline="\n")
        tok = cl.tokenize(testo_prompt)
        voce = dict(c)
        voce.pop("prompt", None)
        voce.pop("prompt_template", None)
        voce["prompt_file"] = pfile.name
        voce["prompt_caratteri"] = len(testo_prompt)
        voce["prompt_sha256"] = sha_testo(testo_prompt)
        voce["prompt_n_token"] = len(tok)
        voce["prompt_ids"] = salva_ids("prompt_%s" % c["id"], tok)
        # impronta del messaggio completo per ciascun contesto: prefisso + domanda
        voce["impronta_per_contesto"] = {}
        for ctx in c["contesti"]:
            pre = c["prefisso_per_contesto"].get(ctx)
            if pre:
                base_sha = prefissi[pre]["sha256_testo"]
                tot = len(tok) + prefissi[pre]["n_token_riverificato"]
            else:
                base_sha = None
                tot = len(tok)
            voce["impronta_per_contesto"][ctx] = {
                "prefisso": pre, "prefisso_sha256": base_sha,
                "token_utente_stimati": tot,
                "sha256_coppia": hashlib.sha256(
                    ((base_sha or "") + "|" + voce["prompt_sha256"]).encode()).hexdigest(),
            }
        casi_out.append(voce)
        print("  %-10s %-22s %6d token" % (c["id"], ",".join(c["insiemi"]), len(tok)), flush=True)

    conteggi = {}
    for c in casi_out:
        for i in c["insiemi"]:
            conteggi[i] = conteggi.get(i, 0) + 1

    manifest = {
        "fase": "P0", "versione": 1, "data_fixture": casi_doc["data"],
        "sigillato": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "secondi_impiegati": round(time.time() - t0, 1),
        "tokenizzatore": {
            "strumento": "endpoint HTTP /tokenize e /detokenize del server in esame",
            "motivo": "llama-tokenize.exe NON e' compilato in questo albero "
                      "(build\\tools\\tokenize contiene solo file di CMake)",
            "url": args.url,
            "nota": "il vocabolario e' quello del GGUF caricato dal binario sotto misura",
        },
        "immutabilita": [
            "il filler e' stato generato una sola volta dai sorgenti del 14/9 e non viene rigenerato",
            "ctx32k/ctx131k/aghi131k sono derivati una sola volta e salvati come testo",
            "per rifare le fixture si crea una nuova cartella con altra data, non si sovrascrive",
        ],
        "filler": {"file": casi_doc["filler"], "sha256": casi_doc["filler_sha256"],
                   "caratteri": casi_doc["filler_caratteri"],
                   "file_sorgente_usati": "filler_file_usati_%s.json" % casi_doc["data"]},
        "codice_copia": {"file": casi_doc["codice_copia"], "sha256": casi_doc["codice_copia_sha256"],
                         "caratteri": len(codice)},
        "prefissi": prefissi,
        "conteggi_per_insieme": conteggi,
        "totale_casi": len(casi_out),
        "istruzione_contesto": casi_doc["istruzione_contesto"],
        "casi": casi_out,
    }
    man_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nfixtures_manifest.json scritto: %d casi, %s" % (len(casi_out), conteggi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
