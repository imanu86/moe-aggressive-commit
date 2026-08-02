#!/usr/bin/env python3
"""La curva di capienza: la politica conta, o conta solo quanta memoria c'e'?

Perche' esiste
--------------
I numeri che giustificano il reap-loop vengono TUTTI da una simulazione a **181
slot su 4551**, cioe' il 4% di capienza -- il gradino RAM->VRAM di DwarfStar:

    LRU / FIFO         0,0%     <- la recency e' inutile: il ciclo e' piu'
    casuale           11,1%        lungo della cache
    insieme caldo     28,2%
    Belady (tetto)    47,8%

Ma il reap-loop lavora sul gradino **RAM<->SSD**, e li' la capienza non e' il
4%: la RAM tiene circa il 58% degli esperti. A quella capienza la curva e' tutta
un'altra cosa -- la LRU va a zero solo quando la cache e' molto piu' piccola del
ciclo di riuso, e a meta' capienza non lo e' piu'.

Quindi la domanda che questo script risponde, PRIMA di scrivere qualunque
politica: **a capienza RAM, quanto distano LRU e Belady?**

    se sono vicine  -> il problema e' la capienza, nessuna politica ci salva,
                       e la fase 2 del reap-loop e' gia' falsificata
    se sono lontane -> c'e' spazio per il calore, e quanto vale si legge qui

E' lo stesso ragionamento che router.py fa a 181 slot, spostato sul gradino
giusto. Vedi la memoria "SIMULA prima di misurare".

L'aritmetica della capienza
---------------------------
Non e' indovinata, ma va CONTROLLATA sui numeri veri del modello prima di
fidarsi del risultato:

    esperti totali      43 strati x 256          = 11.008
    byte degli esperti  43 x 1,69 GiB            = 72,7 GiB
    per esperto         72,7 GiB / 11.008        = 6,76 MiB
    RAM per gli esperti ~48 GiB di standby misurati, meno il backbone (~8 GiB)
                        che e' caldo per costruzione                = ~40-48 GiB
    slot equivalenti    40-48 GiB / 6,76 MiB     = 6.060 - 7.270
                                                 = 55% - 66% di 11.008

Il default e' 6400 slot (58%), ma lo script spazza tutta la curva apposta: se
la conclusione cambia fra il 55% e il 66%, non e' una conclusione.

Uso:  python capienza.py <log con [route-ids]> [slot_ram]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import leggi, separa_fasi, lru, fifo, belady, casuale   # noqa: E402

# 43 strati x 256 esperti. Il totale vero si legge dal tracciato, questo e' solo
# il valore atteso per accorgersi se il tracciato e' parziale.
ESPERTI_ATTESI = 43 * 256
SLOT_RAM_DEFAULT = 6400


def insieme_caldo(accessi, capienza):
    """Insieme caldo STATICO: i `capienza` piu' frequenti, deciso in anticipo.

    E' il tetto di qualunque politica per calore che non si adatti nel tempo,
    e sul gradino VRAM faceva 28,2% contro lo 0% della LRU. Vede il futuro
    quanto Belady (sceglie coi conteggi finali), quindi e' un TETTO, non una
    politica realizzabile: serve per sapere se vale la pena inseguirlo.
    """
    from collections import Counter
    caldi = {k for k, _ in Counter(accessi).most_common(capienza)}
    colpi = sum(1 for k in accessi if k in caldi)
    return colpi, len(accessi) - colpi


def tasso(fn, accessi, capienza):
    c, m = fn(accessi, capienza)
    return 100.0 * c / (c + m) if (c + m) else float('nan')


def analizza(percorso, slot_ram=SLOT_RAM_DEFAULT):
    eventi = leggi(percorso)
    if not eventi:
        print("  nessuna riga [route-ids] nel log")
        return

    _, decode = separa_fasi(eventi)
    if not decode:
        print("  nessun evento di decode: la curva vale solo sul decode")
        return

    # chiave = (strato, esperto), nell'ordine di esecuzione
    accessi = [(lay, e) for _tok, lay, ids in decode for e in ids]
    distinti = len(set(accessi))

    print(f"\n  tracciato   {percorso}")
    print(f"  accessi     {len(accessi)} in decode")
    print(f"  distinti    {distinti} coppie (strato,esperto)"
          f"   attesi ~{ESPERTI_ATTESI}")
    if distinti < ESPERTI_ATTESI * 0.5:
        print("  ATTENZIONE: il tracciato copre meno di meta' degli esperti."
              " La curva sopra il numero di distinti e' priva di significato.")

    # La curva. Le capienze sono frazioni del numero di esperti DISTINTI visti,
    # non di 11.008: sopra i distinti ogni politica fa 100% per costruzione e il
    # confronto smette di dire qualcosa.
    print(f"\n  CURVA DI CAPIENZA (decode, {len(accessi)} accessi)")
    print(f"  {'slot':>7} {'%cap':>6}  {'LRU':>7} {'FIFO':>7} {'casuale':>8}"
          f" {'caldo':>7} {'Belady':>7}   {'Belady-LRU':>11}")
    quote = [0.02, 0.04, 0.08, 0.15, 0.25, 0.40, 0.55, 0.70, 0.85, 1.00]
    for q in quote:
        cap = max(1, int(distinti * q))
        t_lru = tasso(lru, accessi, cap)
        t_fifo = tasso(fifo, accessi, cap)
        t_cas = tasso(casuale, accessi, cap)
        t_cal = tasso(insieme_caldo, accessi, cap)
        t_bel = tasso(belady, accessi, cap)
        print(f"  {cap:>7} {100*q:>5.0f}%  {t_lru:>6.1f}% {t_fifo:>6.1f}%"
              f" {t_cas:>7.1f}% {t_cal:>6.1f}% {t_bel:>6.1f}%   {t_bel-t_lru:>10.1f}")

    # Il punto che decide.
    cap = min(slot_ram, distinti)
    t_lru = tasso(lru, accessi, cap)
    t_cal = tasso(insieme_caldo, accessi, cap)
    t_bel = tasso(belady, accessi, cap)
    print(f"\n  AL GRADINO RAM<->SSD  ({cap} slot = {100.0*cap/distinti:.0f}%"
          f" degli esperti visti)")
    print(f"    LRU (cio' che Windows fa gia')   {t_lru:5.1f}%")
    print(f"    insieme caldo statico (tetto)    {t_cal:5.1f}%")
    print(f"    Belady (tetto assoluto)          {t_bel:5.1f}%")
    print(f"    spazio per una politica          {t_bel - t_lru:5.1f} punti"
          f"   (caldo-contro-LRU: {t_cal - t_lru:+.1f})")
    if t_bel - t_lru < 5.0:
        print("\n    -> a questa capienza la politica NON e' la leva: anche")
        print("       vedendo il futuro si guadagnano meno di 5 punti. La fase 2")
        print("       del reap-loop va rimessa in discussione PRIMA di scriverla.")
    else:
        print(f"\n    -> c'e' spazio: {t_bel - t_lru:.0f} punti fra quel che fa")
        print("       Windows e il tetto. Quanto valgano in t/s e' un'altra")
        print("       misura (sul gradino VRAM un punto valeva ~0,7%).")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    analizza(sys.argv[1],
             int(sys.argv[2]) if len(sys.argv) > 2 else SLOT_RAM_DEFAULT)
