"""Track REAP-ds4 — corpus PUBBLICO surrogato per la replica del ramo-dominio.

Obiettivo (task #16): dimostrare che il finding REAP-K50-lossless-su-dominio NON
dipende dalla KB privata BonusX. Serve un corpus PUBBLICO (nessun dato proprietario)
che il router di DS4-Flash "veda stretto quanto" il dominio Segnali: task ripetitivo,
output strutturato (come l'estrazione promo -> JSON).

Firme di routing target (misurate sulla trace BonusX committata, riprodotte da disco
con scripts/reap_neff.py su runs/reap/2026-07-05_trace_dominio/trace_dominio.tgz):
  n_eff@64 count-based ~46, gate-weight ~40 (range citato 40-47), reuse prev-token
  same-layer ~0.39.

Candidati (entrambi PUBBLICI e 100% generabili da template -> nessuna fonte esterna,
regenerabili byte-identici da un reviewer):
  - candA "prodotto_json": scheda prodotto e-commerce italiana sintetica -> estrai JSON
    (nome, marca, prezzo, categoria, disponibilita', specifiche). E' l'analogo piu'
    fedele dell'estrazione promo->JSON: stesso SHAPE (testo IT breve semi-strutturato
    -> JSON con campi fissi), zero dati reali.
  - candB "ricetta_json": ricetta di cucina italiana sintetica -> estrai JSON
    (titolo, porzioni, tempo, ingredienti[], passi[]). Task ripetitivo alternativo con
    output strutturato piu' lungo (liste), utile se candA non centra l'equivalenza.

Due partizioni DISGIUNTE per seme fisso:
  - TRACE  (16 extract + 4 "explain" lunghi) -> prompt per la trace routing sul pod.
  - EVAL   (10 chunk ppl) -> corpus di valutazione, item DIVERSI da quelli in TRACE
           (anti-overfit della mask sul suo set di calibrazione, come reap_build_eval_corpora).

Tutto e' generato in modo deterministico (seed) e COMMITTATO (testi + manifest sha256):
essendo pubblico/sintetico, il reviewer regenera e verifica l'integrita' end-to-end.

Uso:
  python scripts/reap_public_replica_corpus.py --cand prodotto_json
  python scripts/reap_public_replica_corpus.py --cand ricetta_json
"""
import argparse
import hashlib
import json
import os
import random

BASE = os.path.join(os.path.dirname(__file__), "..", "runs", "reap", "public_replica")

# ---------------------------------------------------------------- vocab pubblico
MARCHE = ["Aurelia", "Montefiore", "Belcanto", "Ferroni", "Valdarno", "Sanpietro",
          "Corvara", "Lentini", "Bormio", "Griffoni", "Tavernelli",
          "Roccabruna", "Dellamora", "Pallavicini", "Sartori", "Bergamasco"]
CATEGORIE = ["scarpe da corsa", "zaino da trekking", "cuffie wireless", "caffettiera",
             "giacca antipioggia", "monitor 27 pollici", "borraccia termica",
             "tastiera meccanica", "materasso matrimoniale", "bicicletta da citta'",
             "aspirapolvere", "smartwatch", "tenda da campeggio", "friggitrice ad aria",
             "sedia ergonomica", "power bank"]
COLORI = ["nero", "blu notte", "grigio antracite", "verde oliva", "rosso mattone",
          "bianco panna", "azzurro", "sabbia"]
MATERIALI = ["alluminio", "poliestere riciclato", "acciaio inox", "cotone organico",
             "policarbonato", "gomma naturale", "nylon balistico", "legno di faggio"]
DISPO = ["disponibile", "in arrivo", "esaurito", "prenotabile", "ultimi pezzi"]
CITTA = ["Milano", "Torino", "Bologna", "Firenze", "Napoli", "Bari", "Padova",
         "Genova", "Verona", "Trieste"]

INGREDIENTI = ["farina 00", "uova", "zucchero", "burro", "latte intero", "lievito",
               "sale fino", "olio extravergine", "pomodori pelati", "basilico",
               "parmigiano", "aglio", "cipolla", "carote", "sedano", "vino bianco",
               "riso Carnaroli", "brodo vegetale", "zafferano", "pancetta",
               "guanciale", "pecorino", "pepe nero", "prezzemolo"]
PIATTI = ["Risotto allo zafferano", "Pasta alla carbonara", "Ragu' alla bolognese",
          "Torta di mele", "Minestrone di verdure", "Frittata di zucchine",
          "Tiramisu' classico", "Polenta concia", "Pesto alla genovese",
          "Zuppa di ceci", "Crostata di marmellata", "Gnocchi al pomodoro",
          "Lasagne al forno", "Insalata di farro", "Vellutata di zucca", "Panna cotta"]
AZIONI = ["mescolare", "cuocere a fuoco lento", "aggiungere", "sfumare con", "tritare",
          "far riposare", "scolare", "mantecare", "impastare", "infornare"]

SYS_EXTRACT = ("Sei un estrattore. Leggi la scheda e restituisci SOLO un oggetto JSON "
               "con i campi indicati, senza testo aggiuntivo.")
SYS_RICETTA = ("Sei un estrattore di ricette. Leggi il testo e restituisci SOLO un "
               "oggetto JSON con titolo, porzioni, tempo_minuti, ingredienti (lista) "
               "e passi (lista), senza testo aggiuntivo.")

EXPLAIN_PROD = ("Spiega passo passo, in italiano, come valuteresti la convenienza di "
                "questo prodotto per un acquirente attento al rapporto qualita'-prezzo, "
                "i rischi concreti e gli errori da evitare. Sii dettagliato.\n\n{body}")
EXPLAIN_RIC = ("Spiega passo passo, in italiano, la tecnica ottimale per preparare "
               "questo piatto senza errori, i punti critici e le varianti utili. "
               "Sii dettagliato.\n\n{body}")


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def prodotto_scheda(rng):
    marca = rng.choice(MARCHE)
    cat = rng.choice(CATEGORIE)
    modello = f"{marca} {cat.split()[0].capitalize()}{rng.randint(100, 999)}"
    prezzo = round(rng.uniform(19.9, 499.0), 2)
    sconto = rng.choice([0, 0, 10, 15, 20, 25, 30])
    colore = rng.choice(COLORI)
    mat = rng.choice(MATERIALI)
    peso = round(rng.uniform(0.2, 4.5), 2)
    disp = rng.choice(DISPO)
    citta = rng.choice(CITTA)
    gar = rng.choice([12, 24, 24, 36])
    body = (f"Scheda prodotto — {modello}\n"
            f"Categoria: {cat}. Marca: {marca}. Colore: {colore}. "
            f"Materiale principale: {mat}. Peso: {peso} kg. "
            f"Prezzo di listino: {prezzo} euro"
            + (f", sconto {sconto}% attivo" if sconto else "") + ". "
            f"Disponibilita': {disp}. Spedizione da {citta}. "
            f"Garanzia {gar} mesi. "
            f"Codice: {marca[:3].upper()}-{rng.randint(10000, 99999)}.")
    gold = {
        "nome": modello, "marca": marca, "categoria": cat, "colore": colore,
        "materiale": mat, "peso_kg": peso, "prezzo_eur": prezzo,
        "sconto_pct": sconto, "disponibilita": disp, "garanzia_mesi": gar,
    }
    task = ("Estrai: nome, marca, categoria, colore, materiale, peso_kg, prezzo_eur, "
            "sconto_pct, disponibilita, garanzia_mesi.")
    return SYS_EXTRACT, f"{task}\n\n{body}", json.dumps(gold, ensure_ascii=False)


def ricetta_scheda(rng):
    titolo = rng.choice(PIATTI)
    porz = rng.choice([2, 4, 4, 6, 8])
    tempo = rng.choice([15, 20, 30, 40, 45, 60, 90])
    ings = rng.sample(INGREDIENTI, k=rng.randint(5, 8))
    passi = []
    for _ in range(rng.randint(4, 6)):
        a = rng.choice(AZIONI)
        obj = rng.choice(ings)
        passi.append(f"{a} {obj}")
    body = (f"Ricetta: {titolo}. Per {porz} persone, tempo {tempo} minuti.\n"
            f"Ingredienti: " + ", ".join(ings) + ".\n"
            f"Preparazione: " + "; ".join(passi) + ".")
    gold = {"titolo": titolo, "porzioni": porz, "tempo_minuti": tempo,
            "ingredienti": ings, "passi": passi}
    return SYS_RICETTA, f"Estrai la ricetta in JSON.\n\n{body}", json.dumps(gold, ensure_ascii=False)


GENS = {
    "prodotto_json": (prodotto_scheda, EXPLAIN_PROD),
    "ricetta_json": (ricetta_scheda, EXPLAIN_RIC),
}
N_TRACE_EXTRACT = 16
N_TRACE_EXPLAIN = 4
N_EVAL_CHUNKS = 10
EVAL_ITEMS_PER_CHUNK = 4    # ~4 schede/chunk -> ~750-850 tok/chunk come i chunk BonusX


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", choices=list(GENS), required=True)
    ap.add_argument("--seed", type=int, default=20260706)
    a = ap.parse_args()
    gen, explain_tmpl = GENS[a.cand]
    rng = random.Random(a.seed)

    base = os.path.join(BASE, a.cand)
    pdir = os.path.join(base, "prompts")
    cdir = os.path.join(base, "corpus")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(cdir, exist_ok=True)

    manifest = {"candidate": a.cand, "seed": a.seed,
                "generator": "scripts/reap_public_replica_corpus.py",
                "license": "synthetic/public — template-generated, no external source",
                "target_routing": {"n_eff64_count_bonusx": 46.4,
                                   "n_eff64_weighted_bonusx": 39.6,
                                   "reuse_prevtok_bonusx": 0.395,
                                   "source": "runs/reap/2026-07-05_trace_dominio/"
                                             "trace_dominio.tgz via scripts/reap_neff.py"},
                "trace_prompts": [], "eval_chunks": []}

    # --- TRACE prompts (extract + explain) ---
    def emit_prompt(name, kind, sys_p, user_p, n_tok):
        text = sys_p + "\n\n" + user_p
        with open(os.path.join(pdir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["trace_prompts"].append(
            {"file": name, "kind": kind, "chars": len(text),
             "n_decode_target": n_tok, "sha256": sha(text)})

    for j in range(N_TRACE_EXTRACT):
        sys_p, user_p, _gold = gen(rng)
        emit_prompt(f"p{j:02d}_extract.txt", "extract", sys_p, user_p, 320)
    for j in range(N_TRACE_EXPLAIN):
        sys_p, user_p, _gold = gen(rng)
        # trasforma in prompt "explain" lungo (decode 300-500 tok) sullo stesso body
        body = user_p.split("\n\n", 1)[1]
        emit_prompt(f"p{16 + j:02d}_explain.txt", "explain",
                    "Sei un consulente esperto.", explain_tmpl.format(body=body), 512)

    # --- EVAL chunks (DISGIUNTI: item generati DOPO, dallo stesso stream rng) ---
    for ci in range(N_EVAL_CHUNKS):
        parts = []
        for _ in range(EVAL_ITEMS_PER_CHUNK):
            sys_p, user_p, gold = gen(rng)
            parts.append(user_p + "\n" + gold)
        text = "\n\n".join(parts)
        name = f"dom_chunk{ci}.txt"
        with open(os.path.join(cdir, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        manifest["eval_chunks"].append(
            {"file": name, "items": EVAL_ITEMS_PER_CHUNK,
             "chars": len(text), "sha256": sha(text)})

    with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)

    tt = sum(p["chars"] for p in manifest["trace_prompts"])
    tc = sum(c["chars"] for c in manifest["eval_chunks"])
    print(f"[{a.cand}] trace prompts: {len(manifest['trace_prompts'])} "
          f"({tt} char), eval chunks: {len(manifest['eval_chunks'])} "
          f"({tc} char, ~{tc // 3.6:.0f} tok stimati)")
    print("dir:", base)
    print("manifest:", os.path.join(base, "manifest.json"))


if __name__ == "__main__":
    main()
