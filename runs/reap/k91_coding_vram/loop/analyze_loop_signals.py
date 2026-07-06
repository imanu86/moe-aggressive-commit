"""REAP-loop Tier A — analisi sensore: il distress e' visibile dall'esterno e PRECEDE il collasso?

Input:
  trace_k91.csv / trace_k0.csv  (pos,layer,n,e0..e5,w0..w5; decode-only, patch 0006)
  gen_k91.log / gen_k0.log      (testo generato, per l'onset della degenerazione)
  reap_mask_coding_k91.json     (keep-list per il segnale di massa controfattuale)

Segnali:
  S1 (da K0 + keep91): massa di gate per token che cade su expert POTATI da K91
     = quanto "vuole" gli expert mancanti il modello full su questo task. Nota: e' il
     segnale che un ds4 patchato potrebbe loggare LIVE (il router calcola tutte le prob
     anche mascherato); qui lo stimiamo offline dalla run full (proxy, dichiarato).
  S2 (da K91): periodicita' del routing = Jaccard medio per-layer dei top-6 tra token
     consecutivi (rolling). Disponibile OGGI a runtime senza patch.
  S3 (da K91): concentrazione dei pesi (share di w0 su 1.5).
Onset testo: primo punto in cui un n-gram di >=4 parole si ripete >=3 volte in una
finestra di 60 parole (detector generico, niente frasi hardcoded).
Allineamento testo<->pos: proporzionale sui caratteri (approssimazione dichiarata:
manca il tokenizer ds4 in locale).

Output: loop_signals.json + stampa tabella.
"""
import csv
import json
import re
import sys
from collections import defaultdict

TRACE_K91 = sys.argv[1] if len(sys.argv) > 1 else "trace_k91.csv"
TRACE_K0 = sys.argv[2] if len(sys.argv) > 2 else "trace_k0.csv"
GEN_K91 = sys.argv[3] if len(sys.argv) > 3 else "gen_k91.log"
MASK = sys.argv[4] if len(sys.argv) > 4 else "../reap_mask_coding_k91.json"


def load_trace(path):
    """{pos: {layer: ([experts], [pesi])}} liste ALLINEATE (slot s -> e_s, w_s)."""
    data = defaultdict(dict)
    with open(path) as f:
        rd = csv.reader(f)
        header = next(rd)
        iw0 = header.index("w0")
        for row in rd:
            if len(row) < iw0 + 6:
                continue
            try:
                pos, layer, n = int(row[0]), int(row[1]), int(row[2])
                es, ws = [], []
                for s in range(n):
                    e = int(row[3 + s])
                    w = float(row[iw0 + s])
                    if e >= 0 and w == w:
                        es.append(e)
                        ws.append(w)
            except (ValueError, IndexError):
                continue
            data[pos][layer] = (es, ws)
    return dict(sorted(data.items()))


def gen_text(path):
    """Testo generato: righe non-ds4 del log, senza il progress prefill."""
    raw = open(path, "rb").read().decode("utf-8", "replace").replace("\r", "\n")
    out = []
    for ln in raw.split("\n"):
        if ln.startswith("ds4:") or "prefill layer" in ln or ln.startswith("=== "):
            continue
        ln = re.sub(r"ds4: CUDA loading model tensors.*", "", ln)
        out.append(ln)
    return "\n".join(out).strip()


def degeneration_onset(text):
    """Ritorna (char_onset|None): prima posizione dove un 4-gram di parole si
    ripete >=3 volte nelle successive 60 parole."""
    words = [(m.group(0), m.start()) for m in re.finditer(r"\S+", text)]
    for i in range(len(words) - 4):
        gram = " ".join(w for w, _ in words[i:i + 4]).lower()
        cnt = 1
        j = i + 4
        while j < min(i + 60, len(words) - 4):
            if " ".join(w for w, _ in words[j:j + 4]).lower() == gram:
                cnt += 1
                j += 4
            else:
                j += 1
        if cnt >= 3:
            return words[i][1]
    return None


def s1_counterfactual_mass(tr_k0, keep):
    """per pos: frazione della massa di gate su expert fuori keep91."""
    out = {}
    for pos, layers in tr_k0.items():
        tot = pruned = 0.0
        for layer, (es, ws) in layers.items():
            k = keep.get(str(layer))
            if k is None:
                continue
            kset = set(k)
            for e, w in zip(es, ws):
                tot += w
                if e not in kset:
                    pruned += w
        if tot > 0:
            out[pos] = pruned / tot
    return out


def s2_route_jaccard(tr):
    """per coppia di pos consecutivi: Jaccard medio sui layer condivisi."""
    poss = list(tr.keys())
    out = {}
    for a, b in zip(poss, poss[1:]):
        js = []
        for layer in tr[a]:
            if layer in tr[b]:
                sa, sb = set(tr[a][layer][0]), set(tr[b][layer][0])
                if sa | sb:
                    js.append(len(sa & sb) / len(sa | sb))
        if js:
            out[b] = sum(js) / len(js)
    return out


def s3_top_weight_share(tr):
    out = {}
    for pos, layers in tr.items():
        shares = []
        for _, (es, ws) in layers.items():
            if ws and sum(ws) > 0:
                shares.append(max(ws) / sum(ws))
        if shares:
            out[pos] = sum(shares) / len(shares)
    return out


def rolling(d, w=10):
    ks = list(d.keys())
    return {k: sum(d[x] for x in ks[max(0, i - w + 1):i + 1]) / len(ks[max(0, i - w + 1):i + 1])
            for i, k in enumerate(ks)}


def main():
    keep = json.load(open(MASK))["keep"]
    tr91, tr0 = load_trace(TRACE_K91), load_trace(TRACE_K0)
    txt91 = gen_text(GEN_K91)

    onset_char = degeneration_onset(txt91)
    n_pos91 = len(tr91)
    poss91 = list(tr91.keys())
    onset_pos = None
    if onset_char is not None and len(txt91) > 0:
        onset_pos = poss91[min(int(onset_char / len(txt91) * n_pos91), n_pos91 - 1)]

    s1 = rolling(s1_counterfactual_mass(tr0, keep))
    s2_91, s2_0 = rolling(s2_route_jaccard(tr91)), rolling(s2_route_jaccard(tr0))
    s3_91, s3_0 = rolling(s3_top_weight_share(tr91)), rolling(s3_top_weight_share(tr0))

    def seg(d, lo, hi):
        vals = [v for k, v in d.items() if lo <= k < hi]
        return round(sum(vals) / len(vals), 4) if vals else None

    p0 = poss91[0]
    res = {
        "decode_tokens": {"k91": n_pos91, "k0": len(tr0)},
        "onset": {"char": onset_char, "pos_approx": onset_pos,
                  "token_index_approx": (poss91.index(onset_pos) if onset_pos in poss91 else None),
                  "nota": "allineamento char->token proporzionale (no tokenizer locale)"},
        "S1_massa_su_potati_da_K0": {
            "media_globale": round(sum(s1.values()) / max(len(s1), 1), 4),
            "nota": "frazione del gate-weight full che cade su expert potati da K91 (0=coperto, 1=tutto fuori)"},
        "S2_jaccard_routing_consecutivo": {
            "k91_prima_onset": seg(s2_91, p0, onset_pos) if onset_pos else None,
            "k91_dopo_onset": seg(s2_91, onset_pos, 10**9) if onset_pos else None,
            "k91_globale": round(sum(s2_91.values()) / max(len(s2_91), 1), 4),
            "k0_globale": round(sum(s2_0.values()) / max(len(s2_0), 1), 4)},
        "S3_share_top_weight": {
            "k91_prima_onset": seg(s3_91, p0, onset_pos) if onset_pos else None,
            "k91_dopo_onset": seg(s3_91, onset_pos, 10**9) if onset_pos else None,
            "k0_globale": round(sum(s3_0.values()) / max(len(s3_0), 1), 4)},
        "serie": {"s1": {str(k): round(v, 4) for k, v in s1.items()},
                   "s2_k91": {str(k): round(v, 4) for k, v in s2_91.items()},
                   "s3_k91": {str(k): round(v, 4) for k, v in s3_91.items()}},
    }
    json.dump(res, open("loop_signals.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "serie"}, indent=1))


if __name__ == "__main__":
    main()
