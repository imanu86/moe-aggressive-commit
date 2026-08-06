# Costo di un passo Jacobi sul 3060 ibrido, dalle costanti GIA' misurate (ledger 5-6/8):
#   curva working-set (finestra -> esperti distinti): 1:258, 8:1244, 16:1993, 32:2962, 128:5220
#   PCIe 24,35 GiB/s; esperto IQ2_XXS = 1,70 GiB/258 = 6,60 MiB
#   parte non-esperti ~64 ms/passo (63,7 "il resto", batcha una volta)
#   metro autoregressivo 8,04 t/s (124,4 ms/token)
# Ipotesi TUTTE a favore di Jacobi: FLOP GPU gratis (sovrapposti), dedup perfetta,
# banda piena, taglia batch della forma ACCOPPIATA (piu' piccola).
import math, sys

CURVA = [(1,258),(8,1244),(16,1993),(32,2962),(128,5220)]
MS_PER_ESPERTO = (6.60/1024)/24.35*1000  # ~0.2647 ms
FISSO_MS = 64.0
METRO_TS = 8.04

def distinti(finestra):
    if finestra <= 1: return 258
    for (x0,y0),(x1,y1) in zip(CURVA, CURVA[1:]):
        if finestra <= x1:
            f = (math.log(finestra)-math.log(x0))/(math.log(x1)-math.log(x0))
            return y0 + (y1-y0)*f
    return CURVA[-1][1]

def batch_accoppiato(W,N,g):
    return 1 + g*(N-1) + (W-1) + W*(N-2)

def riga(W,N,G,g_tipico,quota_cache):
    B = batch_accoppiato(W,N,g_tipico)
    d = distinti(B)
    d_eff = d*(1-quota_cache)
    passo_ms = FISSO_MS + d_eff*MS_PER_ESPERTO
    pareggio = METRO_TS*passo_ms/1000.0
    return B, d, passo_ms, pareggio

print(f"{'config':<16}{'batch':>6}{'distinti':>9}{'passo_ms':>10}{'pareggio tok/passo':>20}")
for (W,N,G,g,cache,nota) in [
    (15,5,15, 8, 0.00, "mandato, senza cache"),
    (15,5,15, 8, 0.35, "mandato, cache 35%"),
    ( 4,3, 4, 2, 0.00, "piccolo, senza cache"),
    ( 4,3, 4, 2, 0.35, "piccolo, cache 35%"),
    ( 2,3, 2, 1, 0.00, "minimo, senza cache"),
    ( 2,3, 2, 1, 0.35, "minimo, cache 35%"),
    ( 2,3, 2, 1, 0.65, "minimo, cache 65% (irrealistico)"),
]:
    B,d,ms,pareggio = riga(W,N,G,g,cache)
    print(f"W{W:<2}N{N}G{G:<10}{B:>6}{d:>9.0f}{ms:>10.0f}{pareggio:>14.2f}      {nota}")
print()
print("Lettura: 'pareggio' = token/passo (1+accettati) necessari per eguagliare 8,04 t/s.")
print("Max fisico per passo = N (1 emesso + N-1 accettati). N=5 -> max 5; N=3 -> max 3.")
