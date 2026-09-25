"""Genera i preset della matrice Q36 (25/9) da A0 (upstream) e B1 (runtime-q36) presi come stampi.

Bracci:
  A0  upstream b10734, Q4_K_M, testa MTP separata Q4_0, n-max 2          (stampo, gia' scritto a mano)
  A1  upstream b10734, UD-IQ3_XXS di unsloth, testa MTP INTERNA, n-max 2
  B0  runtime-q36 elastico, Q4_K_M, senza MTP
  B1  runtime-q36 elastico, Q4_K_M, testa separata Q4_0, n-max 2         (stampo, gia' scritto a mano)
  B2  runtime-q36 elastico, Q4_K_M, testa separata Q8_0, n-max 2
  C0  runtime-q36 elastico, UD-IQ3_XXS, senza MTP
  C1  runtime-q36 elastico, UD-IQ3_XXS, testa INTERNA, n-max 2
  C2  runtime-q36 elastico, UD-IQ3_XXS, testa separata Q8_0, n-max 2 (la interna resta caricata ma inerte)
Nei bracci IQ3 del runtime elastico gli esperti dello strato MTP interno (blk.40) vanno in CUDA0_Mapped:
RAM bloccata letta dalla GPU, fuori dalla VRAM e fuori dalla cache (CUDA0_Mapped non e' host di difetto).
"""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q4 = r"D:\models\qwen36moe\Qwen3.6-35B-A3B-Q4_K_M.gguf"
IQ3 = r"D:\models\qwen36moe\Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf"
MTP_Q4 = r"D:\models\qwen36moe\mtp-Qwen3.6-35B-A3B-Q4_0.gguf"
MTP_Q8 = r"D:\models\qwen36moe\mtp-Qwen3.6-35B-A3B-Q8_0.gguf"
MAPPED_MTP = r"blk\.40\.ffn_(up|gate|down)_exps\.weight=CUDA0_Mapped"

a0 = json.loads((HERE / "preset_Q36_A0_upstream_mtp.json").read_text(encoding="utf-8"))
b1 = json.loads((HERE / "preset_Q36_B1_elastico_mtp.json").read_text(encoding="utf-8"))


def togli(args, flag, n_valori=1):
    """Rimuove un flag e i suoi valori dalla lista degli argomenti."""
    out, i = [], 0
    while i < len(args):
        if args[i] == flag:
            i += 1 + n_valori
            continue
        out.append(args[i])
        i += 1
    return out


def senza_bozza(args):
    for flag in ("--spec-draft-model", "--spec-draft-ngl", "--spec-draft-override-tensor", "--spec-draft-n-max",
                 "--spec-draft-p-min", "-ctkd", "-ctvd", "--model-draft", "--gpu-layers-draft"):
        args = togli(args, flag)
    i = args.index("--spec-type")
    args[i + 1] = "none"
    return args


def interna(args):
    """Testa MTP interna al file: draft-mtp senza modello di bozza."""
    args = togli(args, "--spec-draft-model")
    args = togli(args, "--spec-draft-override-tensor")
    args = togli(args, "--spec-draft-ngl")
    return args


def con_mapped_mtp(args):
    i = args.index("--n-cpu-moe")
    return args[:i] + ["-ot", MAPPED_MTP] + args[i:]


def scrivi(p, nome):
    (HERE / nome).write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(nome, p["etichetta"])


# A1: upstream, IQ3 con testa interna
p = copy.deepcopy(a0)
p.update(id="Q36_A1", etichetta="q36_upstream_fit_iq3xxs_mtpint_n2")
p["descrizione"] = ("Upstream b10734 senza modifiche, UD-IQ3_XXS di unsloth con la testa MTP DENTRO il file, "
                    "-fit on, bozza n-max 2. Riferimento upstream per il ramo IQ3.")
p["args"] = togli(togli(p["args"], "--model-draft"), "--gpu-layers-draft")
p["percorsi"]["MODEL"], p["percorsi"]["DRAFT"] = IQ3, ""
scrivi(p, "preset_Q36_A1_upstream_iq3_mtpint.json")

# B0: elastico Q4_K_M senza MTP
p = copy.deepcopy(b1)
p.update(id="Q36_B0", etichetta="q36_elastico_q4km_nomtp", mtp=False)
p["descrizione"] = "runtime-q36 elastico, Q4_K_M, SENZA MTP: misura il contributo della bozza sullo stesso runtime."
p["speculativa"] = {"modalita": "spenta", "spec_types": None, "n_max": None, "n_min": None, "p_min": None}
p["args"] = senza_bozza(p["args"])
p["percorsi"]["DRAFT"] = ""
scrivi(p, "preset_Q36_B0_elastico_nomtp.json")

# B2: elastico Q4_K_M, testa separata Q8_0
p = copy.deepcopy(b1)
p.update(id="Q36_B2", etichetta="q36_elastico_q4km_mtpq8_n2")
p["descrizione"] = "Come B1 ma con la testa MTP separata Q8_0 di ggml-org (1,99 GB) al posto della Q4_0."
p["percorsi"]["DRAFT"] = MTP_Q8
scrivi(p, "preset_Q36_B2_elastico_mtpq8.json")

# C0: elastico IQ3 senza MTP
p = copy.deepcopy(b1)
p.update(id="Q36_C0", etichetta="q36_elastico_iq3xxs_nomtp", mtp=False)
p["descrizione"] = ("runtime-q36 elastico, UD-IQ3_XXS di unsloth, SENZA MTP. Gli esperti dello strato MTP interno "
                    "(blk.40) in CUDA0_Mapped per non togliere VRAM alla cache.")
p["speculativa"] = {"modalita": "spenta", "spec_types": None, "n_max": None, "n_min": None, "p_min": None}
p["args"] = con_mapped_mtp(senza_bozza(p["args"]))
p["percorsi"]["MODEL"], p["percorsi"]["DRAFT"] = IQ3, ""
scrivi(p, "preset_Q36_C0_elastico_iq3_nomtp.json")

# C1: elastico IQ3 con testa interna
p = copy.deepcopy(b1)
p.update(id="Q36_C1", etichetta="q36_elastico_iq3xxs_mtpint_n2")
p["descrizione"] = ("runtime-q36 elastico, UD-IQ3_XXS di unsloth con la testa MTP INTERNA (draft-mtp senza modello di "
                    "bozza), esperti di blk.40 in CUDA0_Mapped, bozza n-max 2.")
p["args"] = con_mapped_mtp(interna(p["args"]))
p["percorsi"]["MODEL"], p["percorsi"]["DRAFT"] = IQ3, ""
scrivi(p, "preset_Q36_C1_elastico_iq3_mtpint.json")

# C2: elastico IQ3 con testa separata Q8_0
p = copy.deepcopy(b1)
p.update(id="Q36_C2", etichetta="q36_elastico_iq3xxs_mtpq8_n2")
p["descrizione"] = ("runtime-q36 elastico, UD-IQ3_XXS con la testa separata Q8_0 di ggml-org; la testa interna resta "
                    "caricata ma inerte (esperti di blk.40 in CUDA0_Mapped).")
p["args"] = con_mapped_mtp(p["args"])
p["percorsi"]["MODEL"], p["percorsi"]["DRAFT"] = IQ3, MTP_Q8
scrivi(p, "preset_Q36_C2_elastico_iq3_mtpq8.json")

# B3 / C3: testa MTP Q8_0 CONDIVISA (senza token_embd/output, usa quelli del bersaglio) sul runtime Q36s
RUNTIME_S = r"D:\ds4_work\elastico_q36s\runtime-q36s"
MTP_S = r"D:\models\qwen36moe\mtp-Qwen3.6-35B-A3B-shared-Q8_0.gguf"
for base, nome, ide, et in (("preset_Q36_B2_elastico_mtpq8.json", "preset_Q36_B3_elastico_mtpq8s.json",
                             "Q36_B3", "q36_elastico_q4km_mtpq8shared_n2"),
                            ("preset_Q36_C2_elastico_iq3_mtpq8.json", "preset_Q36_C3_elastico_iq3_mtpq8s.json",
                             "Q36_C3", "q36_elastico_iq3xxs_mtpq8shared_n2")):
    p = json.loads((HERE / base).read_text(encoding="utf-8"))
    p.update(id=ide, etichetta=et, binari=RUNTIME_S)
    p["descrizione"] = ("Come " + base + " ma con la testa Q8_0 CONDIVISA (mtp-...-shared-Q8_0.gguf, senza token_embd/"
                        "output: embedding e LM head del bersaglio via ctx_other) sul runtime Q36s.")
    p["percorsi"]["DRAFT"] = MTP_S
    scrivi(p, nome)

def variante_lunga(nome):
    """Copia per il profilo lungo_131k: il prefisso ctx131k e' ~131.248 token, serve contesto > 131072."""
    p = json.loads((HERE / nome).read_text(encoding="utf-8"))
    p.update(id=p["id"] + "L", etichetta=p["etichetta"] + "_ctx132k", contesto=135168)
    scrivi(p, nome.replace(".json", "_L.json"))


# Varianti M3 (politica a banda morta, cache tenuta nel prefill se l'area entra) di B1 e C1:
# stesso preset, binari runtime-q36m3 (M3 + patch Q36). LLAMA_MOE_ELASTIC_M3 non impostata = M3 acceso.
RUNTIME_M3 = r"D:\ds4_work\elastico_q36_m3\runtime-q36m3"
for base, nome in (("preset_Q36_B1_elastico_mtp.json", "preset_Q36_B1m3_elastico_mtp.json"),
                   ("preset_Q36_C1_elastico_iq3_mtpint.json", "preset_Q36_C1m3_elastico_iq3_mtpint.json")):
    p = json.loads((HERE / base).read_text(encoding="utf-8"))
    p.update(id=p["id"] + "m3", etichetta=p["etichetta"] + "_m3", binari=RUNTIME_M3)
    p["descrizione"] = "Variante M3 (banda morta) di " + base + ": " + p["descrizione"]
    scrivi(p, nome)

# Finalisti della fase 2 (lungo_131k): contesto 135168
for nome in ("preset_Q36_A0_upstream_mtp.json", "preset_Q36_A1_upstream_iq3_mtpint.json", "preset_Q36_B1_elastico_mtp.json",
             "preset_Q36_C0_elastico_iq3_nomtp.json", "preset_Q36_C1_elastico_iq3_mtpint.json",
             "preset_Q36_C1m3_elastico_iq3_mtpint.json"):
    variante_lunga(nome)
