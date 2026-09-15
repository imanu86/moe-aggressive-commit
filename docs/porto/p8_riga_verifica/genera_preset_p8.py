"""P8 - genera i preset del banco che puntano ai binari P8.

Perche' uno script e non nove file scritti a mano: i preset differiscono dai due
riferimenti (preset_A.json = spento, preset_M1_p7.json = bozza 1, preset_M2_p7.json
= bozza 2) SOLO per i binari e per le variabili delle leve. Derivarli per copia
garantisce che nessun'altra manopola cambi per distrazione, e le barre rovesciate
dei percorsi passano da Python, non da un heredoc (regola di metodo del 6-7/9).

DUE insiemi di binari, entrambi compilati da `D:\\ds4_work\\p8_work\\source`
(copia dello snapshot P0, senza le patch P3-P7):

  bin_nudo   = build NUDA, nessuna patch P8. Da' R0 (MTP spento -> T1) e R1
               (MTP bozza 1), i due riferimenti a 131k.
  build\\bin  = build con A+B+C+D1 applicate, TUTTE dietro una variabile e tutte
               spegnibili. Le quattro celle cumulative sono quindi quattro
               configurazioni dello STESSO binario: la differenza fra due celle
               e' una variabile, non una compilazione (regola
               `batterie-a-caldo-non-bracci-freddi`, e intento dichiarato del
               progetto per A e per C).

Le quattro leve, con il loro valore di DEFAULT nel binario patchato:

  A   GGML_SCHED_SPLIT_INPUTS     non impostata -> 30 (spenta). Accesa a 96.
  B   QWEN4EXP_QSA_BIAS_DEV       non impostata -> accesa. Spenta con 0.
  C   GGML_CUDA_GETROWS_NARROW    non impostata -> accesa. Spenta con 0.
  D1  QWEN4EXP_QSA_ONE_TRANSPOSE  non impostata -> accesa. Spenta con 0.

Ogni preset scrive TUTTE e quattro esplicitamente: un preset deve dire tutto,
non affidarsi al default di una patch.

  python genera_preset_p8.py
"""
import json
import io
from pathlib import Path

QUI = Path(__file__).resolve().parent
BANCO = QUI.parent / "banco_p0"
BIN_NUDO = r"D:\ds4_work\p8_work\bin_nudo"
BIN_LEVE = r"D:\ds4_work\p8_work\build\bin"

SPENTE = {"QWEN4EXP_QSA_BIAS_DEV": "0",
          "GGML_CUDA_GETROWS_NARROW": "0",
          "QWEN4EXP_QSA_ONE_TRANSPOSE": "0"}


def leve(a=False, b=False, c=False, d1=False):
    e = dict(SPENTE)
    if a:
        e["GGML_SCHED_SPLIT_INPUTS"] = "96"
    if b:
        e["QWEN4EXP_QSA_BIAS_DEV"] = "1"
    if c:
        e["GGML_CUDA_GETROWS_NARROW"] = "1"
    if d1:
        e["QWEN4EXP_QSA_ONE_TRANSPOSE"] = "1"
    return e


# (file, id, etichetta, base, binari, env_extra, patch_nel_binario, descrizione)
CELLE = [
    ("preset_P8_0_p7.json", "P8_0", "p8_r0_spento_binari_nudi",
     "preset_A.json", BIN_NUDO, {}, [],
     "P8 riferimento R0. preset_A.json (MTP SPENTO) sui binari P8 NUDI (nessuna patch). "
     "Serve a dare T1, il costo di un forward a UNA riga, alla profondita' 131k."),

    ("preset_P8_1_p7.json", "P8_1", "p8_r1_mtp1_binari_nudi",
     "preset_M1_p7.json", BIN_NUDO, {}, [],
     "P8 riferimento R1. preset_M1_p7.json (MTP bozza 1, 2 righe di verifica) sui binari "
     "P8 NUDI. E' il metro di paragone di tutte le leve: impronte, R, ms/token, t/s."),

    ("preset_P8_2_p7.json", "P8_2", "p8_leva_a_split_inputs",
     "preset_M1_p7.json", BIN_LEVE, leve(a=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 1 - leva A sola: tetto degli ingressi di split da 30 a 96 "
     "(GGML_SCHED_SPLIT_INPUTS=96). B, C e D1 sono nel binario ma SPENTE."),

    ("preset_P8_3_p7.json", "P8_3", "p8_leva_ab_bias_residente",
     "preset_M1_p7.json", BIN_LEVE, leve(a=True, b=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 2 - leve A+B: piu' il bias QSA copiato una volta sola sul backend di "
     "calcolo (QWEN4EXP_QSA_BIAS_DEV=1). C e D1 SPENTE."),

    ("preset_P8_4_p7.json", "P8_4", "p8_leva_abc_getrows_stretto",
     "preset_M1_p7.json", BIN_LEVE, leve(a=True, b=True, c=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 3 - leve A+B+C: piu' il blocco di get_rows quantizzato stretto alla riga "
     "(GGML_CUDA_GETROWS_NARROW=1). D1 SPENTA."),

    ("preset_P8_5_p7.json", "P8_5", "p8_leva_abcd1_una_trasposta",
     "preset_M1_p7.json", BIN_LEVE, leve(a=True, b=True, c=True, d1=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 4 - leve A+B+C+D1: piu' una sola trasposta del punteggio per forward al "
     "posto di una per token, e un reshape al posto del secondo cont(transpose(...)) "
     "(QWEN4EXP_QSA_ONE_TRANSPOSE=1)."),

    ("preset_P8_6_p7.json", "P8_6", "p8_bozza2_tutte_le_leve",
     "preset_M2_p7.json", BIN_LEVE, leve(a=True, b=True, c=True, d1=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 5 - bozza a 2 token (3 righe di verifica) con tutte le leve accese. "
     "Si apre solo se R e' sceso: la soglia di pareggio della seconda posizione e' "
     "(H + R)/ms-per-token, da confrontare con l'accettazione della posizione 2."),

    ("preset_P8_8_p7.json", "P8_8", "p8_leve_bc_senza_a",
     "preset_M1_p7.json", BIN_LEVE, leve(b=True, c=True),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 6 - B+C SENZA A. Il progetto sostiene che B rende A ridondante: togliendo "
     "le 48 viste del bias gli ingressi scendono sotto il tetto di 30 e il grafo torna a "
     "un lancio da solo. Se R qui e' quello di A+B+C, la patch su ggml-backend.cpp non "
     "serve e la patch finale si accorcia di un file."),

    ("preset_P8_9_p7.json", "P8_9", "p8_consigliata_default_della_patch",
     "preset_M1_p7.json", BIN_LEVE, {},
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 cella 7 - la configurazione CONSIGLIATA, cioe' i soli default della patch, senza "
     "NESSUNA variabile delle leve nel preset: A spenta (tetto 30), B accesa, C accesa, D1 "
     "spenta. Serve a provare che 'applicare la patch e non impostare niente' da' la "
     "configurazione migliore misurata, cioe' che i default sono quelli giusti."),

    ("preset_P8_7_p7.json", "P8_7", "p8_controllo_leve_tutte_spente",
     "preset_M1_p7.json", BIN_LEVE, leve(),
     ["p8_A.patch", "p8_B.patch", "p8_B_interruttore.patch", "p8_C.patch", "p8_D1.patch"],
     "P8 controllo. Binario patchato con TUTTE le leve spente: per costruzione percorre "
     "lo stesso codice del binario nudo, quindi deve riprodurre P8_1 (impronte e, entro "
     "il rumore, R). Se non lo fa, una delle patch non e' davvero spegnibile."),
]


def main():
    scritti = []
    for nome, pid, etichetta, base, binari, env_extra, patch, desc in CELLE:
        d = json.loads((BANCO / base).read_text(encoding="utf-8"))
        d["id"] = pid
        d["etichetta"] = etichetta
        d["fase"] = "P8"
        d["descrizione"] = desc
        d["binari"] = binari
        d["derivato_da"] = base
        d["leve_p8"] = {
            "patch_nel_binario": patch,
            "env_aggiunte_rispetto_alla_base": env_extra,
            "stato_delle_leve": {
                "A_tetto_ingressi_di_split": env_extra.get("GGML_SCHED_SPLIT_INPUTS", "30 (spenta)"),
                "B_bias_qsa_residente": env_extra.get("QWEN4EXP_QSA_BIAS_DEV", "assente nel binario"),
                "C_getrows_stretto": env_extra.get("GGML_CUDA_GETROWS_NARROW", "assente nel binario"),
                "D1_una_trasposta": env_extra.get("QWEN4EXP_QSA_ONE_TRANSPOSE", "assente nel binario"),
            },
        }
        for k, v in env_extra.items():
            d["env"][k] = v
        d["deviazioni_dal_lanciatore_quotidiano"] = list(
            d.get("deviazioni_dal_lanciatore_quotidiano", [])) + [
            "binari NUOVI compilati da D:\\ds4_work\\p8_work\\source (copia dello snapshot P0, "
            "senza le patch P3-P7): le leve P8 non le richiedono e non devono mescolarsi"]
        testo = json.dumps(d, indent=1, ensure_ascii=False)
        # senza BOM, fine riga LF: il banco legge con encoding='utf-8'
        with io.open(BANCO / nome, "w", encoding="utf-8", newline="\n") as f:
            f.write(testo + "\n")
        scritti.append((nome, pid, base, Path(binari).name,
                        ",".join("%s=%s" % kv for kv in sorted(env_extra.items())) or "-"))
    for s in scritti:
        print("%-22s %-6s <- %-20s bin=%-10s %s" % s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
