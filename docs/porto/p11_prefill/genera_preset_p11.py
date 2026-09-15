"""P11 - genera i preset W0..W5 a partire da preset_V3_p10.json.

Regola: i preset sono CUMULATIVI. Ogni cella aggiunge una sola manopola al
candidato precedente; se una cella non paga, la manopola non entra nella
successiva (in quel caso si rigenera con --base).

Scrive JSON UTF-8 SENZA BOM in docs/porto/banco_p0/.
Uso:  python genera_preset_p11.py
"""
import json
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"
BIN_P11 = r"D:\ds4_work\p11_work\bin"

RIFERIMENTO = (
    "prefill freddo a 131k sui binari P8+P10c2+P10c3: 251,92 / 252,16 t/s "
    "(20260915_173505 e 20260915_180825, L01@ctx131k, prompt_n 131248, cache_n 0). "
    "Decode dello stesso candidato V3: 27,42 / 27,36 t/s. Impronta L01 99ba1423cf12."
)


def scrivi(nome, preset):
    p = BANCO / nome
    testo = json.dumps(preset, indent=1, ensure_ascii=False)
    p.write_text(testo + "\n", encoding="utf-8")   # utf-8 semplice: nessun BOM
    print("scritto %s (%d byte)" % (p, p.stat().st_size))


def imposta_arg(args, chiave, valore):
    a = list(args)
    for i, v in enumerate(a):
        if v == chiave:
            a[i + 1] = valore
            return a
    raise SystemExit("argomento %s non trovato" % chiave)


def main():
    base = json.loads((BANCO / "preset_V3_p10.json").read_text(encoding="utf-8"))

    def nuovo(idw, etichetta, descrizione, env_extra=None, batch=None, differenze=None):
        p = json.loads(json.dumps(base))          # copia profonda
        p["id"] = idw
        p["etichetta"] = etichetta
        p["descrizione"] = descrizione
        p["fase"] = "P11"
        p["binari"] = BIN_P11
        p["riferimento"] = RIFERIMENTO
        p["derivato_da"] = "preset_V3_p10.json"
        p["differenze_da_V3"] = differenze
        if env_extra:
            p["env"].update(env_extra)
        if batch:
            p["args"] = imposta_arg(p["args"], "-b", str(batch))
            p["args"] = imposta_arg(p["args"], "-ub", str(batch))
        p["deviazioni_dal_lanciatore_quotidiano"] = [
            "host 127.0.0.1 invece di 0.0.0.0: il banco non deve esporre il server in rete",
            "avvio diretto dell'eseguibile, senza .bat (regola di metodo 8/9)",
            "nessun pause finale (regola di metodo 7/9)",
            "log su file dedicato con prefisso p0_",
            "binari: copia CONGELATA dei binari P8+P10c2+P10c3 in " + BIN_P11
            + " (nessuna ricompilazione in P11: le leve GDN a tile e staging sono gia'"
            + " nell'albero e gia' nei binari, verificate per nome nelle DLL)",
        ]
        return p

    comune = ("Punto operativo P11: prefill FREDDO di 131.072 token (profilo prefill_131k),"
              " MTP spento, 64 slot, KV 262144, greedy seed 1234, ragionamento acceso,"
              " risposta brevissima (64 token). ")

    scrivi("preset_W0_p11.json", nuovo(
        "W0", "p11_w0_riferimento_v3",
        comune + "W0 = preset V3 com'e' (nessuna manopola di prefill accesa): stabilisce il"
        " riferimento del profilo su questi binari. Atteso ~250-252 t/s.",
        differenze="nessuna leva nuova: sparse FA spenta, batch 2048, GDN a tile spento,"
                   " staging degli esperti spento. Cambiano solo il percorso dei binari"
                   " (copia congelata) e il profilo del banco."))

    scrivi("preset_W1_p11.json", nuovo(
        "W1", "p11_w1_sparse_fa",
        comune + "W1 = W0 + sparse flash attention a teste 256. Atteso ~295 t/s"
        " (+18,1% misurato il 13/9 a 131k, con testo identico byte per byte).",
        env_extra={"QWEN4EXP_SPARSE_FA": "1"},
        differenze="QWEN4EXP_SPARSE_FA passa da 0 a 1."))

    scrivi("preset_W2_p11.json", nuovo(
        "W2", "p11_w2_sparse_fa_batch4096",
        comune + "W2 = W1 + batch e ubatch a 4096. A 32k il passaggio 2048->4096 valeva"
        " 327->410 t/s; a 131k il rischio e' la VRAM (a batch 2048 la workspace arriva"
        " gia' a 4408 MiB con ~390 MiB liberi a fine prefill).",
        env_extra={"QWEN4EXP_SPARSE_FA": "1"}, batch=4096,
        differenze="QWEN4EXP_SPARSE_FA=1 (da W1) e -b/-ub da 2048 a 4096."))

    scrivi("preset_W2b_p11.json", nuovo(
        "W2b", "p11_w2b_sparse_fa_batch3072",
        comune + "W2b = ripiego di W2: batch e ubatch a 3072, se 4096 sfonda la VRAM.",
        env_extra={"QWEN4EXP_SPARSE_FA": "1"}, batch=3072,
        differenze="QWEN4EXP_SPARSE_FA=1 (da W1) e -b/-ub da 2048 a 3072."))


if __name__ == "__main__":
    main()
