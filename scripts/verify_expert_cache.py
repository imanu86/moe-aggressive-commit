"""verify_expert_cache.py — verifica il MOTORE slice-cache degli expert su OLMoE vero.

Tre check (sul modello reale allenai/OLMoE-1B-7B-0924-Instruct, caricato in bf16 su CPU):

  1) ALWAYS-FETCH LOSSLESS: stessa generazione greedy con
       (A) cache PIENA  (capacity=64, tutti gli expert residenti, nessun evict) e
       (B) cache PICCOLA (capacity=8 + working-set pinnato).
     I pesi sono gli STESSI, gestiti diversamente: i token generati devono essere IDENTICI.

  2) VRAM-EXPERT: con la cache PICCOLA misura torch.cuda.memory_allocated dovuto alle slice di
     expert residenti -> deve essere MOLTO < 14 GB (un modello da ~14GB che gira con pochi GB di
     VRAM-expert). Si riportano i GB con cache piccola vs piena.

  3) STATS: hits/misses coerenti; fetched_bytes > 0 con cache piccola, ~0 (solo eventuale setup) con
     cache piena dopo il warm-up.

Uso (PowerShell):
    $env:PYTHONPATH = "C:\\Users\\imanu\\source\\repos\\moe-aggressive-commit\\src"
    python scripts\\verify_expert_cache.py
"""

from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from msc.hierarchy.olmoe_cache import install_expert_cache

HF = "allenai/OLMoE-1B-7B-0924-Instruct"
PROMPT = "Explain in one sentence why the sky is blue."
MAX_NEW = 24
_GB = float(1 << 30)


def _vram_expert_gb(handle) -> float:
    """VRAM (GB) occupata dalle SOLE slice di expert residenti in cache (somma su tutti i layer).

    Indipendente da memory_allocated globale: conta le slice GPU davvero tenute dalle cache, cosi la
    misura riflette esattamente la VRAM-expert (il numero che dimostra la capacita').
    """
    total_bytes = 0
    for cache in handle._caches.values():  # noqa: SLF001 (introspezione voluta in verifica)
        for gu, dn in cache._resident.values():  # noqa: SLF001
            total_bytes += gu.element_size() * gu.numel()
            total_bytes += dn.element_size() * dn.numel()
    return total_bytes / _GB


def _load_model():
    tok = AutoTokenizer.from_pretrained(HF)
    # bf16, su CPU. NESSUN device_map/offload di accelerate: la gestione device e' di install_expert_cache.
    model = AutoModelForCausalLM.from_pretrained(HF, dtype=torch.bfloat16)
    model.eval()
    return tok, model


def _build_resident(model, n_per_layer: int) -> dict[int, set[int]]:
    """Working-set pinnato fisso (cieco): expert 0..n-1 per ogni layer."""
    n_layers = int(model.config.num_hidden_layers)
    return {i: set(range(n_per_layer)) for i in range(n_layers)}


@torch.no_grad()
def _greedy_generate(model, enc, device) -> torch.Tensor:
    enc = {k: v.to(device) for k, v in enc.items()}
    out = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False)
    return out[0].detach().to("cpu")


def main() -> int:
    if not torch.cuda.is_available():
        print("[FATAL] CUDA non disponibile: la verifica richiede la GPU.")
        return 2
    device = torch.device("cuda")

    tok, model = _load_model()
    n_layers = int(model.config.num_hidden_layers)
    n_experts = int(model.config.num_experts)
    top_k = int(model.config.num_experts_per_tok)
    print(f"[cfg] n_layers={n_layers} n_experts={n_experts} top_k={top_k} "
          f"hidden={model.config.hidden_size} inter={model.config.intermediate_size}")

    enc = tok(PROMPT, return_tensors="pt")

    # ---- byte di un expert (gate_up + down) in fp16, per il calcolo del 'modello pieno' ----
    e0 = model.model.layers[0].mlp.experts
    bytes_per_expert_fp16 = (e0.gate_up_proj[0].numel() + e0.down_proj[0].numel()) * 2
    full_expert_gb = bytes_per_expert_fp16 * n_experts * n_layers / _GB
    print(f"[size] expert totali (fp16) = {full_expert_gb:.2f} GB  "
          f"(bytes/expert={bytes_per_expert_fp16/1e6:.2f} MB)")

    # ======================================================================
    # (A) CACHE PIENA: capacity=64, tutti pinnati -> lossless 'always-resident'
    # ======================================================================
    print("\n=== (A) cache PIENA: capacity=64, tutti gli expert residenti ===")
    resident_full = {i: set(range(n_experts)) for i in range(n_layers)}
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    handle_full = install_expert_cache(model, capacity_per_layer=n_experts,
                                       resident_by_layer=resident_full, device=device)
    vram_full_expert_gb = _vram_expert_gb(handle_full)
    alloc_full_gb = torch.cuda.memory_allocated() / _GB
    tokens_full = _greedy_generate(model, enc, device)
    stats_full = handle_full.stats()
    text_full = tok.decode(tokens_full, skip_special_tokens=True)
    print(f"    VRAM-expert (slice residenti) = {vram_full_expert_gb:.2f} GB | "
          f"torch.cuda.memory_allocated = {alloc_full_gb:.2f} GB")
    print(f"    stats: hits={stats_full['total']['hits']} misses={stats_full['total']['misses']} "
          f"fetched_gb={stats_full['fetched_gb']:.3f} fetch_rate={stats_full['fetch_rate']:.4f} "
          f"resident_experts={stats_full['resident_experts']}")
    print(f"    testo: {text_full!r}")
    handle_full.remove()
    del handle_full
    torch.cuda.empty_cache()

    # ======================================================================
    # (B) CACHE PICCOLA: capacity=8 + working-set pinnato (es. 4)
    # ======================================================================
    SMALL_CAP = 8
    PIN_N = 4
    print(f"\n=== (B) cache PICCOLA: capacity={SMALL_CAP}, pinned={PIN_N}/layer ===")
    resident_small = _build_resident(model, PIN_N)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    handle_small = install_expert_cache(model, capacity_per_layer=SMALL_CAP,
                                        resident_by_layer=resident_small, device=device)
    vram_small_expert_gb_pre = _vram_expert_gb(handle_small)
    tokens_small = _greedy_generate(model, enc, device)
    vram_small_expert_gb = _vram_expert_gb(handle_small)
    alloc_small_gb = torch.cuda.memory_allocated() / _GB
    peak_small_gb = torch.cuda.max_memory_allocated() / _GB
    stats_small = handle_small.stats()
    text_small = tok.decode(tokens_small, skip_special_tokens=True)
    print(f"    VRAM-expert (slice residenti) = {vram_small_expert_gb:.3f} GB "
          f"(pre-gen {vram_small_expert_gb_pre:.3f} GB) | "
          f"memory_allocated={alloc_small_gb:.2f} GB peak={peak_small_gb:.2f} GB")
    print(f"    stats: hits={stats_small['total']['hits']} misses={stats_small['total']['misses']} "
          f"fetched_gb={stats_small['fetched_gb']:.3f} fetch_rate={stats_small['fetch_rate']:.4f} "
          f"resident_experts={stats_small['resident_experts']}")
    # esempio per-layer (layer 0)
    print(f"    stats per_layer[0] = {stats_small['per_layer'][0]}")
    print(f"    testo: {text_small!r}")
    handle_small.remove()

    # ======================================================================
    # VERDETTI
    # ======================================================================
    lossless = torch.equal(tokens_full, tokens_small)
    # 'nuovi token' generati (escludendo il prompt) per un confronto piu' leggibile
    n_prompt = enc["input_ids"].shape[1]
    gen_full = tokens_full[n_prompt:].tolist()
    gen_small = tokens_small[n_prompt:].tolist()

    under_budget = vram_small_expert_gb < 14.0
    # stats coerenti: piccola deve avere fetched_bytes>0 e misses>0; piena ~0 fetch dopo warm-up.
    stats_coherent = (
        stats_small["total"]["misses"] > 0
        and stats_small["total"]["fetched_bytes"] > 0
        and stats_full["total"]["misses"] == 0
        and stats_full["total"]["fetched_bytes"] == 0
        and (stats_small["total"]["hits"] + stats_small["total"]["misses"]) > 0
    )

    print("\n=== RISULTATI ===")
    print(f"[1] always-fetch LOSSLESS (token cap64 == token cap8): {lossless}")
    if not lossless:
        print(f"    gen_full  = {gen_full}")
        print(f"    gen_small = {gen_small}")
    print(f"[2] VRAM-expert cache piccola = {vram_small_expert_gb:.3f} GB  "
          f"(< 14 GB: {under_budget}) | cache piena = {vram_full_expert_gb:.2f} GB")
    print(f"[3] stats coerenti (piccola: miss>0 & fetch>0; piena: 0/0): {stats_coherent}")
    print(f"    esempio fetch stats (cache piccola) = {{'hits': {stats_small['total']['hits']}, "
          f"'misses': {stats_small['total']['misses']}, "
          f"'fetched_gb': {stats_small['fetched_gb']:.3f}, "
          f"'fetch_rate': {stats_small['fetch_rate']:.4f}}}")

    ok = bool(lossless and under_budget and stats_coherent)
    print(f"\nALL_OK = {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
