"""Sim velocita' 3060 per V4-Flash: quanto guadagna rimpicciolire lo STATICO (attention) e/o gli EXPERT
(temperature-quant), e quanto pesa il path I/O (WSL-vhdx vs NVMe nativo). ANCORATO al dato reale:
cache 151 expert -> 0.49 tok/s (misurato con --nothink su RTX 3060).
Modello streaming-bound: t/token = static_read_VRAM + misses*expert_bytes/BW_io + compute(trascurabile).
"""
import numpy as np

VRAM=12.0; KV=0.7; RESERVE=1.5          # GB: KV + buffer streaming (con prefill-chunk 512)
L=43; ACTIVE_PER_LAYER=6; NEED=L*ACTIVE_PER_LAYER   # 258 expert-attivazioni/token
E_TOTAL=256*L                            # 11008 expert totali
EXP_MB={ '2bit':6.75, '1.58bit':6.75*1.58/2.3, '1bit':6.75*1.0/2.3 }  # ds4: 6.75MB/expert a 2-bit (2.3bpw eff)
VRAM_BW=320.0                            # GB/s lettura statico da VRAM
# --- ANCORA: cache 151 expert -> 0.49 t/s. Assumo BW_io(WSL-vhdx) ~0.72 GB/s (random-read vhdx) e ricavo la miss ---
ANCHOR_N=151; ANCHOR_TPS=0.49; BW_WSL=0.72
def calibrate_miss_at_anchor(exp_mb):
    t=1.0/ANCHOR_TPS                     # s/token
    static_t=STATIC_CUR/VRAM_BW          # lettura statico (VRAM) per token
    fetch_t=t-static_t                   # tempo speso in fetch
    miss_bytes=fetch_t*BW_WSL            # GB fetchati
    misses=miss_bytes*1000/exp_mb
    return misses/NEED                   # miss-rate all'ancora
STATIC_CUR=10.0                          # GB statico attuale (Q8/F16), misurato ~10
m_anchor=None

def miss_rate(N, m_anchor, alpha=0.75):
    """miss decade con la cache: power-law calibrata sull'ancora. N=cache expert totali."""
    if N<=ANCHOR_N: return min(0.98, m_anchor*(ANCHOR_N/max(N,1))**alpha)
    return max(0.02, m_anchor*(ANCHOR_N/N)**alpha)

def tok_s(static_gb, exp_mb, bw_io, alpha=0.75, temp_frac_cold=0.0, cold_mb=None):
    cache_gb=max(0.2, VRAM-static_gb-KV-RESERVE)
    # se temperature-quant: expert medi piu' piccoli -> piu' ne stanno + fetch piu' leggeri
    avg_mb=exp_mb if temp_frac_cold==0 else exp_mb*(1-temp_frac_cold)+cold_mb*temp_frac_cold
    N=cache_gb*1000/avg_mb
    m=miss_rate(N, m_anchor, alpha)
    misses=NEED*m
    fetch_t=misses*avg_mb/1000/bw_io
    static_t=static_gb/VRAM_BW
    t=static_t+fetch_t+0.02              # +compute spannometrico
    return 1.0/t, N, m

# calibra
exp2=EXP_MB['2bit']
m_anchor=calibrate_miss_at_anchor(exp2)
print(f"Ancora: cache {ANCHOR_N} exp -> {ANCHOR_TPS} t/s  =>  miss-rate calibrata ~{m_anchor:.2f}  (BW WSL-vhdx {BW_WSL} GB/s)\n")

STATIC={'attuale Q8/F16 (~10GB)':10.0, 'static-Q4 (~5.5GB)':5.5, 'static-Q2 (~3GB)':3.0}
IO={'WSL-vhdx (0.72 GB/s)':0.72, 'NVMe nativo (3.5 GB/s)':3.5, 'NVMe top (5 GB/s)':5.0}

print(f"{'STATICO':24} {'I/O path':22} {'cacheExp':>8} {'miss':>6} {'tok/s':>7}")
for io_name,bw in IO.items():
    for st_name,st in STATIC.items():
        tps,N,m=tok_s(st, exp2, bw)
        flag=' <== attuale' if (abs(st-10)<0.1 and 'WSL' in io_name) else ''
        print(f"{st_name:24} {io_name:22} {N:8.0f} {m*100:5.0f}% {tps:7.2f}{flag}")
    print()

print("=== + il TUO temperature-per-expert (freddi a 1-bit, ~68% freddi) ===")
for io_name,bw in [('WSL-vhdx',0.72),('NVMe nativo 3.5',3.5),('NVMe 5',5.0)]:
    tps,N,m=tok_s(5.5, exp2, bw, temp_frac_cold=0.68, cold_mb=EXP_MB['1bit'])
    print(f"  static-Q4 + temp-experts | {io_name:16}: cache {N:.0f} exp, miss {m*100:.0f}%, {tps:.2f} tok/s")
print("\nNOTA: miss calibrata su UN punto reale + decadimento power-law (alpha=0.75). Uso GENERALE (routing sparso)")
print("      => stime prudenti. La leva I/O (uscire dal vhdx WSL) pesa quanto il quant. Da confermare col build vero.")
