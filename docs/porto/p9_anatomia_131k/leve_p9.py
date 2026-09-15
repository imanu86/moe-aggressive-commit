"""P9 - aritmetica delle leve sul token singolo, dai numeri misurati di A e B.

Nessuna leva e' stata eseguita: qui si calcola solo che cosa varrebbe, usando la banda
EFFETTIVA misurata di ogni kernel invece di quella di picco. La regola e': se una leva
toglie byte, il tempo scende della stessa frazione **alla banda effettiva di quel
kernel**, non a quella di picco; se una leva toglie inefficienza, il tetto e' la banda
effettiva del kernel piu' efficiente della stessa famiglia.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VRAM_PICCO = 340.3e9

ns = json.loads((HERE / "log" / "p9_L01_nsys.json").read_text(encoding="utf-8"))
comp = json.loads((HERE / "log" / "p9_composizione.json").read_text(encoding="utf-8"))
ker = {k["kernel"]: k for k in ns["kernel"]}
cat = {c["categoria"]: c for c in ns["categorie"]}
parete = ns["per_forward_ms"]["parete"]

# ---------------------------------------------------------------- byte per famiglia
ATTN = {3, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47}
import re
byte_q6 = byte_q8 = 0
byte_q6_senza_uscita = 0
for t in comp["tensori"]:
    if t["nome"].startswith(("token_embd", "per_layer_token_embd")):
        continue
    if "_exps" in t["nome"] or ".ple_" in t["nome"]:
        continue
    if t["tipo"] == "q6_k":
        byte_q6 += t["byte"]
        if not t["nome"].startswith("output"):
            byte_q6_senza_uscita += t["byte"]
    elif t["tipo"] == "q8_0":
        byte_q8 += t["byte"]

# esperti: 10 instradati per strato
esp = {}
for t in comp["tensori"]:
    m = re.match(r"blk\.(\d+)\.ffn_(gate|up|down)_exps", t["nome"])
    if m:
        esp.setdefault(int(m.group(1)), {})[m.group(2)] = (t["byte"] // 512, t["tipo"])
byte_iq2 = sum(v["gate"][0] + v["up"][0] for v in esp.values() if v["gate"][1] == "iq2_s") * 10
byte_iq3 = sum(v["gate"][0] + v["up"][0] for v in esp.values() if v["gate"][1] == "iq3_s") * 10
byte_iq4 = sum(v["down"][0] for v in esp.values()) * 10

ms_q6 = ker["mul_mat_vec_q<q6_k>"]["ms_per_forward"]
ms_q8 = ker["mul_mat_vec_q<q8_0>"]["ms_per_forward"]
ms_iq2 = ker["mul_mat_vec_q<iq2_s>"]["ms_per_forward"]
ms_iq4 = ker["mul_mat_vec_q<iq4_nl>"]["ms_per_forward"]
ms_iq3 = ker["mul_mat_vec_q<iq3_s>"]["ms_per_forward"]

def gbs(b, ms):
    return b / (ms / 1e3) / 1e9

out = {"parete_ms": parete, "banda_effettiva_gbs": {
    "q6_k denso": round(gbs(byte_q6, ms_q6), 1),
    "q8_0 denso": round(gbs(byte_q8, ms_q8), 1),
    "iq2_s esperti (gate+up)": round(gbs(byte_iq2, ms_iq2), 1),
    "iq4_nl esperti (down)": round(gbs(byte_iq4, ms_iq4), 1),
    "iq3_s esperti": round(gbs(byte_iq3, ms_iq3), 1),
    "picco misurato": round(VRAM_PICCO / 1e9, 1)}}

# ------------------------------------------------- modello a due termini del matvec
# t = byte/banda_di_picco + pesi * costo_di_dequantizzazione(formato)
# I pesi di ogni famiglia si ricavano dai byte e dai bit per peso del formato.
BPW = {"q6_k": 6.5625, "q8_0": 8.5, "iq2_s": 2.5, "iq3_s": 3.4375, "iq4_nl": 4.5,
       "q4_k": 4.5, "q5_k": 5.5}
FAMIGLIE = [("q6_k denso", byte_q6, ms_q6, "q6_k"),
            ("q8_0 denso", byte_q8, ms_q8, "q8_0"),
            ("iq2_s esperti gate+up", byte_iq2, ms_iq2, "iq2_s"),
            ("iq3_s esperti gate+up", byte_iq3, ms_iq3, "iq3_s"),
            ("iq4_nl esperti down", byte_iq4, ms_iq4, "iq4_nl")]
due_termini = {}
for nome, b, ms, tipo in FAMIGLIE:
    pesi = b * 8 / BPW[tipo]
    ps_peso = ms / 1e3 / pesi * 1e12
    ps_byte = b / VRAM_PICCO / pesi * 1e12
    due_termini[nome] = {
        "byte_mib": round(b / (1 << 20), 1), "ms": round(ms, 3),
        "pesi_milioni": round(pesi / 1e6, 1),
        "ps_per_peso_totale": round(ps_peso, 3),
        "ps_per_peso_dai_byte": round(ps_byte, 3),
        "ps_per_peso_di_dequantizzazione": round(ps_peso - ps_byte, 3),
        "quota_dequantizzazione_pct": round(100 * (ps_peso - ps_byte) / ps_peso, 1),
        "bpw_effettivi": round(BPW[tipo] * (VRAM_PICCO / 1e9) / gbs(b, ms), 2)}
out["modello_a_due_termini"] = due_termini

# ------------------------------------------------------------------------- leva 1
b_q6 = gbs(byte_q6, ms_q6)
risparmio_tutto = byte_q6 * (1 - 4.5 / 6.5625)
risparmio_senza_uscita = byte_q6_senza_uscita * (1 - 4.5 / 6.5625)
pesi_q6 = byte_q6 * 8 / 6.5625
deq_q6 = ms_q6 / 1e3 / pesi_q6 - byte_q6 / VRAM_PICCO / pesi_q6
byte_q4k = byte_q6 * 4.5 / 6.5625
# per Q4_K si assume il costo di dequantizzazione di Q6_K (pessimista) e quello di
# IQ4_NL (ottimista): entrambi sono MISURATI qui, non ipotizzati altrove
deq_iq4 = ms_iq4 / 1e3 / (byte_iq4 * 8 / 4.5) - byte_iq4 / VRAM_PICCO / (byte_iq4 * 8 / 4.5)
ms_q4k_pess = (byte_q4k / VRAM_PICCO + pesi_q6 * deq_q6) * 1e3
ms_q4k_ott = (byte_q4k / VRAM_PICCO + pesi_q6 * deq_iq4) * 1e3
out["leva1_q6k_verso_q4k"] = {
    "byte_q6_letti_per_token_mib": round(byte_q6 / (1 << 20), 1),
    "ms_misurati": ms_q6,
    "banda_effettiva_gbs": round(b_q6, 1),
    "byte_tolti_mib": round(risparmio_tutto / (1 << 20), 1),
    "ms_risparmiati_alla_banda_effettiva": round(risparmio_tutto / b_q6 / 1e9 * 1e3, 3),
    "ms_risparmiati_al_pavimento": round(risparmio_tutto / VRAM_PICCO * 1e3, 3),
    "senza_la_testa_di_uscita": {
        "byte_tolti_mib": round(risparmio_senza_uscita / (1 << 20), 1),
        "ms_risparmiati": round(risparmio_senza_uscita / b_q6 / 1e9 * 1e3, 3)},
    "vram_liberata_mib": round(risparmio_tutto / (1 << 20), 1),
    "slot_esperti_in_piu": round(risparmio_tutto / 1971200 / 48, 1),
    "col_modello_a_due_termini": {
        "ms_q4k_col_costo_di_dequantizzazione_del_q6k": round(ms_q4k_pess, 3),
        "ms_q4k_col_costo_di_dequantizzazione_dell_iq4nl": round(ms_q4k_ott, 3),
        "guadagno_ms_intervallo": [round(ms_q6 - ms_q4k_pess, 3), round(ms_q6 - ms_q4k_ott, 3)]},
}

# ------------------------------------------------------------------------- leva 2
piccoli = [k for k in ns["kernel"] if k["us_per_lancio"] < 2.5]
lanci_tot = sum(k["lanci_per_forward"] for k in ns["kernel"])
lanci_p = sum(k["lanci_per_forward"] for k in piccoli)
ms_p = sum(k["ms_per_forward"] for k in piccoli)
# costo di un lancio "vuoto": i kernel con pochissimi blocchi e byte trascurabili
vuoti = [k for k in ns["kernel"] if k["blocchi_medi_per_lancio"] < 30 and k["us_per_lancio"] < 1.5]
us_vuoto = sum(k["ms_per_forward"] for k in vuoti) * 1e3 / sum(k["lanci_per_forward"] for k in vuoti)
out["leva2_lanci"] = {
    "lanci_per_forward": round(lanci_tot, 1),
    "lanci_sotto_2_5_us": round(lanci_p, 1),
    "ms_dei_lanci_piccoli": round(ms_p, 3),
    "us_per_lancio_vuoto_misurato": round(us_vuoto, 2),
    "ms_di_puro_lancio_nei_piccoli": round(lanci_p * us_vuoto / 1e3, 3),
    "gia_fuso": "attn_qkv e' UN tensore nel GGUF; gate/up+GLU sono fusi (mmvq con has_fusion=1, "
                "47 lanci iq2_s per forward = uno per strato invece di due)",
    "bersaglio": "le connessioni HC: build_hc_mix gira 2 volte per strato e mette ~14 nodi "
                 "elementari ciascuna, cioe' ~1.300 lanci per forward",
}

# ------------------------------------------------------------------------- leva 3
b_iq4 = gbs(byte_iq4, ms_iq4)
out["leva3_kernel_esperti"] = {
    "iq2_s": {"mib": round(byte_iq2 / (1 << 20), 1), "ms": ms_iq2,
              "gbs": round(gbs(byte_iq2, ms_iq2), 1),
              "pct_del_picco": round(100 * gbs(byte_iq2, ms_iq2) / (VRAM_PICCO / 1e9), 1),
              "bit_per_peso_dichiarati": 2.5,
              "bit_per_peso_effettivi": round(2.5 * (VRAM_PICCO / 1e9) / gbs(byte_iq2, ms_iq2), 2)},
    "iq4_nl": {"mib": round(byte_iq4 / (1 << 20), 1), "ms": ms_iq4,
               "gbs": round(b_iq4, 1),
               "pct_del_picco": round(100 * b_iq4 / (VRAM_PICCO / 1e9), 1)},
    "se_iq2_s_arrivasse_a_iq4_nl_ms": round(byte_iq2 / b_iq4 / 1e9 * 1e3, 3),
    "guadagno_ms": round(ms_iq2 - byte_iq2 / b_iq4 / 1e9 * 1e3, 3),
    "se_iq2_s_arrivasse_al_picco_ms": round(byte_iq2 / VRAM_PICCO * 1e3, 3),
    "guadagno_massimo_ms": round(ms_iq2 - byte_iq2 / VRAM_PICCO * 1e3, 3),
    "piu_iq4_nl_alla_banda_del_q6k_ms": round(ms_iq4 - byte_iq4 / b_q6 / 1e9 * 1e3, 3),
    "col_modello_a_due_termini": {
        "ms_se_la_dequantizzazione_costasse_come_iq4nl":
            round((byte_iq2 / VRAM_PICCO + (byte_iq2 * 8 / 2.5) * deq_iq4) * 1e3, 3),
        "ms_se_costasse_come_q6k":
            round((byte_iq2 / VRAM_PICCO + (byte_iq2 * 8 / 2.5) * deq_q6) * 1e3, 3)},
}

# ------------------------------------------------------- 4: che cosa cresce col contesto
cresce = {"punteggio QSA sui blocchi (mul_mat_f)": cat["4b. punteggio QSA sui blocchi (mul_mat_f f32)"]["ms_per_forward"],
          "ordinamento dell'indicizzatore": cat["8. indicizzatore QSA: ordinamento (radix sort)"]["ms_per_forward"],
          "copie H2D del bias QSA": ns["copie"]["h2d_ms_per_forward"]}
out["cosa_cresce_col_contesto"] = {
    "voci": {k: round(v, 3) for k, v in cresce.items()},
    "totale_ms_a_131k": round(sum(cresce.values()), 3),
    "quota_del_token_pct": round(100 * sum(cresce.values()) / parete, 2),
    "stima_a_262k_ms": round(sum(cresce.values()) * 2, 3),
    "stima_a_32k_ms": round(sum(cresce.values()) * 32768 / 131248, 3),
    "costante_col_contesto": {"gather delle 2048 celle scelte":
                              cat["7. indicizzatore QSA: gather delle celle (k_get_rows)"]["ms_per_forward"]},
}

# ------------------------------------------------------------------------- tetto
tab = json.loads((HERE / "log" / "p9_tabella_B.json").read_text(encoding="utf-8"))
pav_vram = sum(r["pavimento_ms"] for r in tab["righe"]
               if r["pavimento_ms"] and r["banda_gbs"] and r["banda_gbs"] > 100)
pav_pcie = sum(r["pavimento_ms"] for r in tab["righe"]
               if r["pavimento_ms"] and r["banda_gbs"] and r["banda_gbs"] < 100)
nascosto = ns["per_forward_ms"]["sovrapposizione_fra_kernel"]
out["tetto"] = {
    "pavimento_vram_ms": round(pav_vram, 3),
    "pavimento_pcie_ms": round(pav_pcie, 3),
    "sovrapposizione_gia_ottenuta_ms": nascosto,
    "pavimento_con_la_sovrapposizione_di_oggi_ms": round(pav_vram + pav_pcie - nascosto, 3),
    "pavimento_con_sovrapposizione_perfetta_ms": round(max(pav_vram, pav_pcie), 3),
    "misurato_ms": parete,
    "t_s_al_pavimento_di_oggi": round(1000 / (pav_vram + pav_pcie - nascosto), 2),
    "t_s_con_sovrapposizione_perfetta": round(1000 / max(pav_vram, pav_pcie), 2),
    "t_s_misurato": round(1000 / parete, 2),
}
g1 = out["leva1_q6k_verso_q4k"]["ms_risparmiati_alla_banda_effettiva"]
g3 = out["leva3_kernel_esperti"]["guadagno_ms"]
g2 = 1.2
out["tre_leve_insieme"] = {
    "leva1_ms": round(g1, 2), "leva2_ms": g2, "leva3_ms": round(g3, 2),
    "ms_per_token_atteso": round(parete - g1 - g2 - g3, 2),
    "t_s_atteso": round(1000 / (parete - g1 - g2 - g3), 2),
    "solo_le_lossless_ms": round(parete - g2 - g3, 2),
    "solo_le_lossless_t_s": round(1000 / (parete - g2 - g3), 2),
}

(HERE / "log" / "p9_leve.json").write_text(json.dumps(out, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
print(json.dumps(out, indent=1, ensure_ascii=False))
