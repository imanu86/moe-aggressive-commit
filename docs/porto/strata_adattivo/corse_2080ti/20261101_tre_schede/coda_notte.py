"""Coda notturna 01/11/2026: 3080 Ti e 2080 Ti libere, 3060 con schermo e OktoCGControl.
Banco della comunita' (prompt freschi 4K/32K, 3 corse, T=0, 256 token) sotto bench.lock, porta 8105.
Un braccio fallito non ferma la coda. Non tocca Daily, bat o config della Daily.
Uso: coda_notte.py F1 | F2 ...   (fasi in FASI)."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

QUI = Path(__file__).resolve().parent
LOCK = Path(r'D:\ds4_work\strata\lab_locks\bench.lock')
S = Path(r'D:\ds4_work\strata\Strata')
PY = S / '.venv/Scripts/python.exe'
BENCH = Path(r'C:\Users\imanu\source\repos\Strata-wt\upsync-main\bench\results\2026-09-30-community-rtx-5090\benchmark.py')
CFG = QUI.parent / '20261029_upsync0271' / 'strata-0271-pila-3080ti.json'
B0271 = QUI.parent / '20261004_routed_keep' / 'build-up0271pila-5fbc4784'
B029 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-b6ba3fa6'
B835 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-835f73b2'
B3FF = QUI.parent / '20261004_routed_keep' / 'build-up029pila-3ff7b1db'
BFUS2 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-8cb752a4'   # mega-kernel su tutti i tipi
BT4 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-1fe8e46d'   # tappa 4
BEPD = QUI.parent / '20261004_routed_keep' / 'build-ep5036-bb01432e'   # PR #5036 adattata
BT4B = QUI.parent / '20261004_routed_keep' / 'build-up029pila-c9643043'   # tappa 4b
BP2 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-3422ae78'   # secondo server di esperti
BP3 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-1fe8d044'   # secondo server: salto, quota, stage
BP4 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-020c723e'   # salto corretto, stage
BP6 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-4512b587'   # lettura sul secondo server
BP7 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-076e7d90'   # lettura a ciclo chiuso
BP8 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-4d38da47'   # lettura a ciclo chiuso
BP9 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-bb02371b'   # lettura a ciclo chiuso
BP10 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-38871bec'   # lettura a ciclo chiuso
BFUS = QUI.parent / '20261004_routed_keep' / 'build-up029pila-156240a9'   # mega-kernel del server, STRATA_PEER_FUSED
BEP0 = QUI.parent / '20261004_routed_keep' / 'build-up029pila-8ad3bef3'   # PIPELINE3_PIANO tappa 0: STRATA_PEER_STAMP
BGDN = QUI.parent / '20261004_routed_keep' / 'build-up029pila-bee277a0'   # PR #4876 (xrip): STRATA_GDN_TC=2, GDN a tensor core su sm_75
BEPB = QUI.parent / '20261004_routed_keep' / 'build-up029pila-SHA0B'   # PIPELINE3_PIANO tappa 0b: STRATA_PEER_REFILL_FLUSH, 'adapt ms host' nella riga del peer
BREF = QUI.parent / '20261004_routed_keep' / 'build-up029pila-67908ef8'   # riferimento delle leve sui kernel della 2080 Ti (tappa 0b spenta = bee277a0)
BLEV = QUI.parent / '20261004_routed_keep' / 'build-up029pila-7a837206'   # PR #4942 (IQ3_S/IQ3_XXS interleaved, righe a 0 su sm_75) + STRATA_GU_FUSED_MINB + STRATA_PEER_ONE_COPY, tutte spente
DUE, TRE = '0,2', '0,2,1'   # PCI_BUS_ID: 0=3080 Ti, 1=3060, 2=2080 Ti


def freddi(n):
    """3060 (CUDA1) fuori dalla catena: tiene n esperti fissi tra quelli che le altre due non contengono.
    Niente --remote-expert-opt, che li farebbe ruotare. La 2080 Ti qui e' CUDA2, quindi il suo nucleo RAM passa a DEV2."""
    return {'_args': ['--split-device', '2', '--expert-cache-device1', str(n)], '_togli': ['--prompt-cache-file'],
            'STRATA_RAM_CORE_SLOTS_DEV1': None, 'STRATA_RAM_CORE_SLOTS_DEV2': '5500'}


def confronto(rip):
    """v0.2.9 e v0.2.7.1 alternate, stessa divisione, riserva 700/384."""
    return [(f'{n}{s}_{r}', b, s, DUE, 700, 384, {}) for r in rip for s in ('20', '18', '16', '22')
            for n, b in (('u', B029), ('p', B0271))]


SENZA_CATENA = {'_togli': ['--prompt-cache-file', '--pipeline-windows']}
PIENO = '4096,32768,128000'   # i tre bersagli del banco della comunita'
TUTTE = {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8', 'STRATA_MMVQ_IL': None}
SPIN = {'STRATA_POOL_SPIN_US': None}
TEMPI = {'STRATA_DECODE_TIMING': '1'}
BOZZE0 = {'STRATA_MTP_STAGE0': '1'}
PLE_RAM = {'_args': ['--ple-io', 'ram']}
# bozze sulla 3060, che non fa stadi: la 2080 Ti diventa CUDA2, quindi anche il suo nucleo RAM
TRE_BOZZE = '0,1,2'
SWAP32 = {'_args': ['--adapt-swaps', '32']}
INSIEME = {'STRATA_ADAPT_NOWAIT': '1', 'STRATA_ADAPT_LAG': '2', 'STRATA_KQ_SPLIT': '1', 'STRATA_GU_SWIGLU': '1'}
# 2080 Ti come livello di esperti della 3080 Ti: i due calcolano parti dello stesso strato. Non convive con divisione, catena, elastica e nucleo RAM
EPD = {'_args': ['--expert-parallel-device', '1'], '_togli': ['--layer-split', '--pipeline-windows', '--prompt-cache-file', '--vram-reserve-later-mib'],
       '_togli1': ['--elastic', '--trim-stage-weights'], 'STRATA_ARENA_PIN_GIB': '8', 'STRATA_RAM_CORE': None, 'STRATA_RAM_CORE_SLOTS_DEV1': None,
       'STRATA_CONV_DISK': None, 'STRATA_PREFIX_DISK_MULTI': None}   # PR #5036: rifiuta divisione, catena, peer e cache elastica
PEER = {'_args': ['--peer-device', '1', '--peer-reserve-mib', '3000'],
         '_togli': ['--layer-split', '--pipeline-windows', '--prompt-cache-file', '--vram-reserve-later-mib'],
        '_togli1': ['--elastic', '--trim-stage-weights'], 'STRATA_ARENA_PIN_GIB': '8',   # l'arena intera esaurisce la memoria bloccabile e il flusso CUDA della seconda scheda non si apre
        'STRATA_RAM_CORE': None, 'STRATA_RAM_CORE_SLOTS_DEV1': None,
        'STRATA_CONV_DISK': None, 'STRATA_PREFIX_DISK_MULTI': None}
PEER2 = {**PEER, '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1500']}   # con TRE: 1 = 2080 Ti, 2 = 3060
BOZZE3060 = {'_args': ['--split-device', '2'], 'STRATA_MTP_DEVICE': '1', 'STRATA_RAM_CORE_SLOTS_DEV1': None, 'STRATA_RAM_CORE_SLOTS_DEV2': '5500'}
SM86 = {'STRATA_GU_SWIGLU': '1', 'STRATA_GR_UP75': '1', 'STRATA_CPU_IQ_ALL_EXACT1': '1'}
STAMP = {'STRATA_PEER_STAMP': '1'}   # due stamp %globaltimer sul flusso del peer per strato: lo span GPU del server nella riga 'strata decode peer:'
FLUSH = {'STRATA_PEER_REFILL_FLUSH': '1'}   # tappa 0b: cudaStreamQuery sul flusso refill del peer dopo le copie dell'adattamento + apply_pending a sondaggio dal pool fra gli strati
# leve sui kernel della 2080 Ti (02/11 sera, build 7a837206). PR #4942: la tabella emessa sulla 2080 Ti da' 0 in ogni cella IQ3_S/IQ3_XXS
# (pareggio con native_mmvq nel bench, come #4962), quindi le righe si forzano con STRATA_MMVQ_IL_ROWS (2 righe per warp, come IQ4_XS in
# kIlRows_75; vale per entrambe le schede) e decide il banco. STRATA_GU_FUSED_MINB=4 e' gia' bocciata da native_expert_bench (gate/up +7-10%):
# non entra. STRATA_PEER_ONE_COPY conta solo col peer: FK3.
LEVE = {'STRATA_MMVQ_IL_ROWS': ';'.join(f'{t}:{n}:2,2,2,2,2' for t in (21, 18) for n in (2, 3, 4))}
ONE = {'STRATA_PEER_ONE_COPY': '1'}
CACHE_FISSA = {'_args': ['--adapt-swaps', '0']}   # nessuno scambio di esperti: a T=0 il testo dipende solo dai kernel

# nome, build, split, schede, riserva stadio 0, riserva stadi dopo, env in piu'
FASI = {
    'F1': [
        ('d16_r1393', B0271, '16', DUE, 1393, 384, {}),
        ('d16_r700', B0271, '16', DUE, 700, 384, {}),
        ('d18_r700', B0271, '18', DUE, 700, 384, {}),
        ('d20_r700', B0271, '20', DUE, 700, 384, {}),
        ('d22_r700', B0271, '22', DUE, 700, 384, {}),
        ('d16_r700_b', B0271, '16', DUE, 700, 384, {}),
    ],
    'F2': confronto('ab'),
    'F3': [
        ('t20_44', B0271, '20,44', TRE, 700, 384, {}),
        ('t20_42', B0271, '20,42', TRE, 700, 384, {}),
    ],
    'F4': [   # 384 non basta al secondo verificatore sullo stadio di mezzo
        ('t20_44_l1000', B0271, '20,44', TRE, 700, 1000, {}),
        ('t20_42_l1000', B0271, '20,42', TRE, 700, 1000, {}),
    ],
    'F5': [(f'h20_{n}', B0271, '20', '0,1,2', 700, 384, freddi(n)) for n in (1000, 2000, 4000)],
    'F7': [   # gli esperti freddi spengono catena doppia e nucleo RAM: paragone a due schede senza catena, poi di nuovo con la 3060
        ('n20_a', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file', '--pipeline-windows']}),
        ('f20_2000_b', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('n20_b', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file', '--pipeline-windows']}),
        ('f20_3000', B0271, '20', '0,1,2', 700, 384, freddi(3000)),
    ],
    'F8': [   # 02/11, OktoCGControl chiuso: stesse build delle corse col programma aperto, a coppie alternate
        ('oku20_a', B029, '20', DUE, 700, 384, {}),
        ('okp20_a', B0271, '20', DUE, 700, 384, {}),
        ('okn20_a', B0271, '20', DUE, 700, 384, SENZA_CATENA),
        ('okf20_2000_a', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('okf20_4000_a', B0271, '20', '0,1,2', 700, 384, freddi(4000)),
        ('oku20_b', B029, '20', DUE, 700, 384, {}),
        ('okp20_b', B0271, '20', DUE, 700, 384, {}),
        ('okn20_b', B0271, '20', DUE, 700, 384, SENZA_CATENA),
        ('okf20_2000_b', B0271, '20', '0,1,2', 700, 384, freddi(2000)),
        ('okt20_44', B0271, '20,44', TRE, 700, 1000, {}),
    ],
    'F9': [   # prompt grandi: l'uso vero parte da 30K. 128K = stesso prompt del banco 19/10; la vecchia configurazione e' split 16 con riserva 1393
        (f'g{n}_{r}', b, s, DUE, r0, 384, {'_targets': '64000,128000'}) for r in 'ab' for n, b, s, r0 in
        (('16_vecchia', B0271, '16', 1393), ('20u', B029, '20', 700), ('22u', B029, '22', 700), ('24u', B029, '24', 700))
    ],
    'F10': [   # leve della 2080 Ti mai misurate qui (#2197, #4962), banco comunita' completo, a coppie alternate col riferimento
        (f'L{n}_{r}', B029, '20', DUE, 700, 384, {'_targets': PIENO, **e}) for r in 'ab' for n, e in (
            ('base', {}),
            ('il', {'STRATA_MMVQ_IL': None}),
            ('sm75', {'STRATA_SM75_PERF': '1'}),
            ('sm75m8', {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8'}),
            ('tutte', {'STRATA_SM75_PERF': '1', 'STRATA_EXP_MODE': '8', 'STRATA_MMVQ_IL': None}))
    ],
    'F11': [   # divisioni e vecchia configurazione sul banco completo
        (f'D{n}_{r}', b, s, DUE, r0, 384, {'_targets': PIENO}) for r in 'ab' for n, b, s, r0 in
        (('16vecchia', B0271, '16', 1393), ('22u', B029, '22', 700), ('24u', B029, '24', 700))
    ],
    'F12': [
        # dall'analisi di Fable: lavoratori CPU col valore normale, e i tre interruttori sm_86 che con due architetture il motore non applica
        (f'M{n}_{r}', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, **e}) for r in 'ab' for n, e in (
            ('rif', {}),
            ('spin', SPIN),
            ('sm86', SM86),
            ('spin86', {**SPIN, **SM86}))
    ],
    'F13': [   # OktoCGControl acceso: si confronta solo dentro questa fase. STRATA_VERIFY_PROFILE=1 ha bloccato il motore (Ptempi), qui non c'e'
        ('Ptempi2', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, 'STRATA_DECODE_TIMING': '1'})] + [
        (f'Z{s}tutte_{r}', B029, s, DUE, 700, 384, {'_targets': PIENO, **TUTTE}) for r in 'ab' for s in ('20', '22', '24')
    ],
    'F14': [   # i ~11 ms non scomposti: senza catena la riga dei tempi e' a somma esatta; con soglia 0.35 meno finestre buttate (Ptempi2: 66%)
        ('Pserie', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, **SENZA_CATENA, 'STRATA_DECODE_TIMING': '1'}),
        ('Ptheta35', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, 'STRATA_DECODE_TIMING': '1',
                                                 'STRATA_PIPELINE_DEBUG': '1', 'STRATA_PIPELINE_THETA': '0.35'}),
    ],
    'F15': [   # la riga dei tempi legge solo lo stadio 0 (ver.ms_wait): STRATA_SPLIT_TIMING da' l'attesa di ogni scheda, senza toccare i percorsi
        (f'Pstadi{s}', B029, s, DUE, 700, 384, {'_targets': PIENO, **TUTTE, **SENZA_CATENA, 'STRATA_DECODE_TIMING': '1', 'STRATA_SPLIT_TIMING': '1'})
        for s in ('20', '22', '24')
    ],
    'F16': [   # giro veloce delle leve residue di Fable a contesto lungo (banco_lungo.py), riferimento in testa e in coda: filtra, poi BAB sulle vincenti
        (f'Y{n}_{r}', B029, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **e}) for r in 'a' for n, e in (
            ('rif', {}),
            ('modo8', {'STRATA_SM75_PERF': None}),
            ('piano', {'STRATA_VERIFY_DEVICE_PLAN': '1'}),
            ('ramo', {'STRATA_MTP_SHARED_BRANCH': None}),
            ('nohost', {'_args': ['--no-host-worker']}),
            ('swap32', {'_args': ['--adapt-swaps', '32']}),
            ('bozze0', {'STRATA_MTP_STAGE0': '1'}),
            ('rif2', {}),
        )
    ],
    'F17': [   # sotto carico: va lanciata con carico_cpu.py acceso, conta anche il secondo peggiore
        (f'K{n}_{r}', B029, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **e}) for r in 'a' for n, e in (
            ('rif', {}),
            ('spin', SPIN),
            ('nohost', {'_args': ['--no-host-worker']}),
            ('swap32', {'_args': ['--adapt-swaps', '32']}),
        )
    ],
    'F18': [   # 61 finestre su 95 sono gia' a 4 righe, il massimo: si prova il bordo della finestra a contesto lungo
        (f'S{n}_{r}', B029, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **e}) for r in 'a' for n, e in (
            ('rif', {}),
            ('spec3', {'_args': ['--spec', '3'], '_togli': ['--spec']}),
            ('spec6', {'_args': ['--spec', '6'], '_togli': ['--spec']}),
            ('minp35', {'_args': ['--spec-min-p', '0.35'], '_togli': ['--spec-min-p']}),
            ('minp70', {'_args': ['--spec-min-p', '0.7'], '_togli': ['--spec-min-p']}),
        )
    ],
    'F19': [   # RAM: tabella n-grammi (26,8 GiB) letta dall'SSD invece che tenuta in RAM; piu' esperti fissi sulla 2080 Ti = meno copie in RAM
        (f'R{n}_{r}', B029, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **e}) for r in 'a' for n, e in (
            ('rif', {}),
            ('ple', {'STRATA_PLE_AUTO_RAM': '0'}),
            ('core7000', {'STRATA_RAM_CORE_SLOTS_DEV1': '7000'}),
            ('rif2', {}),
        )
    ],
    'F20': [   # BAB della catena con le bozze sulla prima scheda; il prefisso resta su SSD per configurazione, la seconda volta niente rilettura dei 128K
        (f'B{n}{i}', B029, '20', DUE, 700, 384, {'_lungo': True, '_prefisso': n, **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'bozze', BOZZE0), (2, 'rif', {}), (2, 'bozze', BOZZE0), (3, 'rif', {}),
        )
    ],
    'F21': [   # visione sulla 3060: solo configurazione, nessuna modifica al motore
        ('Vgpu', B029, '20', DUE, 700, 384, {'_lungo': True, '_visione': True, **TUTTE}),
    ],
    'F22': [   # PC appena riavviato, 3060 scarica: gli 87 t/s erano la macchina o l'SSD? Alternate SSD e RAM, poi il banco completo
        (f'C{n}{i}', B029, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'ssd', {}), (1, 'ram', PLE_RAM), (2, 'ssd', {}), (2, 'ram', PLE_RAM),
        )
    ] + [('Cpieno', B029, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, **TEMPI})],
    'F23': [   # BAB a PC riavviato, stessa build per tutti: bozze sulla 3080 Ti e sulla 3060 contro il riferimento, poi il banco completo
        (f'E{n}{i}', B835, '20', sc, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **e}) for i, n, sc, e in (
            (1, 'rif', DUE, {}), (1, 'b0', DUE, BOZZE0), (1, 'b3060', TRE_BOZZE, BOZZE3060),
            (2, 'rif', DUE, {}), (2, 'b0', DUE, BOZZE0), (2, 'b3060', TRE_BOZZE, BOZZE3060),
            (3, 'rif', DUE, {}),
        )
    ] + [('Epieno', B835, '20', DUE, 700, 384, {'_targets': PIENO, **TUTTE, **TEMPI})],
    'F24': [   # prima la seconda scheda come aiuto dentro lo stesso strato, poi BAB col banco completo sulle candidate del giro veloce
        ('Vpeer', B835, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER})] + [
        (f'V{n}{i}', B835, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'b0', BOZZE0), (1, 'swap', SWAP32), (1, 'spin', SPIN),
            (2, 'rif', {}), (2, 'b0', BOZZE0), (2, 'swap', SWAP32), (2, 'spin', SPIN),
            (3, 'rif', {}),
        )
    ],
    'F25': [   # build con la riga delle due meta' della scommessa: STRATA_SA_BET spenta (Fable: 90% perse sulle T=2) e bozze con riuso del prefisso su SSD
        (f'W{n}{i}', B3FF, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'bet0', {'STRATA_SA_BET': '0'}), (2, 'rif', {}), (2, 'bet0', {'STRATA_SA_BET': '0'}),
        )
    ],
    'FEP0': [   # PIPELINE3_PIANO tappa 0: span GPU del server (2080 Ti) a strato con due stamp sul suo flusso (STRATA_PEER_STAMP), con e senza cambio di scheda
        (f'V{n}{i}', BEP0, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **e}) for i, n, e in (
            (1, 'st', STAMP), (1, 'ns', {**STAMP, 'STRATA_PEER_NOSWITCH': '1'}),
            (2, 'st', STAMP), (2, 'ns', {**STAMP, 'STRATA_PEER_NOSWITCH': '1'}),
            (3, 'st', STAMP), (3, 'ns', {**STAMP, 'STRATA_PEER_NOSWITCH': '1'}),
        )
    ],
    'FEP0b': [   # PIPELINE3_PIANO tappa 0b: il join dell'adattamento. Riferimento (pr), flush (fl), meno swap (sw4, sw0), flush a cache fissa (fl0: testo contro sw0)
        (f'V{n}', BEPB, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **e}) for n, e in (
            ('pr1', {}), ('fl1', FLUSH),
            ('sw4', {'_args': ['--adapt-swaps', '4']}), ('sw0', {'_args': ['--adapt-swaps', '0']}),
            ('fl0', {**FLUSH, '_args': ['--adapt-swaps', '0']}),
            ('pr2', {}), ('fl2', FLUSH),
        )
    ],
    'FEP1': [   # span del server col modo degli esperti: 8 di oggi, default Turing (4), 0 con EXPDEC. Se scende sotto 250 us il parallelo vero si riapre
        (f'X{n}{i}', BEP0, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, **e}) for i, n, e in (
            (1, 'm8', {}), (1, 'm4', {'STRATA_EXP_MODE': None}), (1, 'm0', {'STRATA_EXP_MODE': '0'}),
            (2, 'm8', {}), (2, 'm4', {'STRATA_EXP_MODE': None}), (2, 'm0', {'STRATA_EXP_MODE': '0'}),
        )
    ],
    'F27': [   # la tabella sm_86 non si applica con schede miste: mancano i due adattamenti in testa alla tabella (-6,3 punti su A4000 se tolti). Dopo il riavvio delle 22:22
        (f'A{n}{i}', B3FF, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'lag', {'STRATA_ADAPT_NOWAIT': '1', 'STRATA_ADAPT_LAG': '2'}),
            (2, 'rif', {}), (2, 'lag', {'STRATA_ADAPT_NOWAIT': '1', 'STRATA_ADAPT_LAG': '2'}),
            (3, 'rif', {}),
        )
    ],
    'F28': [   # insieme delle leve da tenere sulla 3080 Ti e sulla 2080 Ti contro il riferimento: adattamenti sm_86 + KQ_SPLIT + GU_SWIGLU. Coda staccata dalla sessione
        (f'C{n}{i}', B3FF, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'ins', INSIEME), (2, 'rif', {}), (2, 'ins', INSIEME), (3, 'rif', {}), (3, 'ins', INSIEME),
        )
    ],
    'F29': [   # dove mettere lo schermo togliendo la 3060: 3 GB in meno sulla 3080 Ti (riserva 3700) o sulla 2080 Ti (riserva dopo 3384), config della 0.2.9 nuova
        (f'S{n}{i}', B3FF, '20', DUE, r0, r1, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **INSIEME}) for i, n, r0, r1 in (
            (1, 'rif', 700, 384), (1, 'su3080', 3700, 384), (1, 'su2080', 700, 3384), (2, 'rif', 700, 384),
        )
    ],
    'FEP2': [   # mega-kernel del server (STRATA_PEER_FUSED) contro il peer di oggi, stessa build; in testa e in coda la divisione a strati di riferimento
        ('Qrif1', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
        ('Qpeer1', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP}),
        ('Qfus1', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, 'STRATA_PEER_FUSED': '1'}),
        ('Qpeer2', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP}),
        ('Qfus2', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, 'STRATA_PEER_FUSED': '1'}),
        ('Qrif2', BFUS, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
    ],
    'FEP3': [   # mega-kernel con tutti i 48 strati coperti (8cb752a4) contro il peer di oggi; riferimento a strati in testa e in coda
        ('Grif1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
        ('Gpeer1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP}),
        ('Gfus1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, 'STRATA_PEER_FUSED': '1'}),
        ('Gpeer2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP}),
        ('Gfus2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, 'STRATA_PEER_FUSED': '1'}),
        ('Grif2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
    ],
    'FEP4': [   # mega-kernel acceso: col join dell'adattamento tolto dal giro (STRATA_PEER_REFILL_FLUSH, tappa 0b) e no; riferimento a strati nello stesso formato
        ('Hrif1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
        ('Hfus1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1'}),
        ('Hfl1', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER_REFILL_FLUSH': '1'}),
        ('Hfus2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1'}),
        ('Hfl2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER_REFILL_FLUSH': '1'}),
        ('Hrif2', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **INSIEME}),
    ],
    'FEP5': [   # mega-kernel: quota degli esperti caldi data alla 2080 Ti (STRATA_PEER_HOT, default 0,45 sui primi 8700, pensato per una padrona con ~8700 posti; la 3080 Ti ne ha 2561)
        (f'K{n}', BFUS2, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1', **e}) for n, e in (
            ('h45a', {}), ('h0', {'STRATA_PEER_HOT': '0'}), ('h20', {'STRATA_PEER_HOT': '0.2'}),
            ('h20at', {'STRATA_PEER_HOT': '0.2', 'STRATA_PEER_HOT_AT': '2561'}), ('h45b', {}),
        )
    ],
    'FEP6': [   # tappa 4: lettura a strati + scrittura col mega-kernel, banco completo, contro divisione a strati e mega-kernel da solo
        (f'Z4{n}{i}', BT4, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', INSIEME), (1, 'fus', {**PEER, 'STRATA_PEER_FUSED': '1'}), (1, 'ep', {**PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_EP_SPLIT_PREFILL': '1'}),
            (2, 'ep', {**PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_EP_SPLIT_PREFILL': '1'}), (2, 'rif', INSIEME),
        )
    ],
    'FEP7': [   # PR #5036 (--expert-parallel-device 1) contro la divisione a strati con la stessa build e contro il nostro mega-kernel, banco completo
        ('Yrif1', BEPD, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **INSIEME}),
        ('Yepd1', BEPD, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **EPD}),
        ('Yfus1', BFUS2, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER, 'STRATA_PEER_FUSED': '1'}),
        ('Yepd2', BEPD, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **EPD}),
        ('Yrif2', BEPD, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **INSIEME}),
    ],
    'FEP8': [   # tappa 4b: lettura a strati con i buffer della 2080 Ti in prestito dal tier, contro divisione a strati e mega-kernel da solo
        (f'X4{n}{i}', BT4B, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', INSIEME), (1, 'fus', {**PEER, 'STRATA_PEER_FUSED': '1'}), (1, 'ep', {**PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_EP_SPLIT_PREFILL': '1'}),
            (2, 'ep', {**PEER, 'STRATA_PEER_FUSED': '1', 'STRATA_EP_SPLIT_PREFILL': '1'}), (2, 'rif', INSIEME),
        )
    ],
    'FP2': [   # due server di esperti (2080 Ti + 3060 sul riser, schermo sulla 3060) contro divisione a strati e un server
        (f'P2{n}{i}', BP2, '20', sch, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, sch, e in (
            (1, 'rif', DUE, INSIEME), (1, 'fus', DUE, {**PEER, 'STRATA_PEER_FUSED': '1'}),
            (1, 'due', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '0'}),
            (1, 'duf', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1'}),
            (2, 'duf', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1'}), (2, 'rif', DUE, INSIEME),
        )
    ],
    'FP3': [   # secondo server: salto dei passi vuoti e quota calda, schermo sulla 3060 (stage spento: FAIL al banco)
        (f'P3{n}{i}', BP3, '20', sch, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, sch, e in (
            (1, 'nos', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '0'}),
            (1, 'skp', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1'}),
            (1, 'sh2', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_SHARE': '0.2'}),
            (1, 'sh3', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_SHARE': '0.33'}),
            (1, 'rif', DUE, INSIEME),
        )
    ],
    'FP3B': [   # quota calda al secondo server con il salto spento (il salto cade nel motore: plan mismatch)
        (f'P3{n}{i}', BP3, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER2, 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '0', 'STRATA_PEER2_SHARE': f}) for i, n, f in (
            (1, 'q2', '0.2'), (1, 'q3', '0.33'),
        )
    ],
    'FP4': [   # salto corretto e righe q8_1 sul riser, schermo sulla 3060
        (f'P4{n}{i}', BP4, '20', sch, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, sch, e in (
            (1, 'nos', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '0'}),
            (1, 'skp', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1'}),
            (1, 'stg', TRE, {**PEER2, 'STRATA_PEER_FUSED': '1', 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1'}),
            (1, 'rif', DUE, INSIEME),
        )
    ],
    'FP4B': [   # tappa 4b (lettura a strati, buffer in prestito) con i due server di esperti, salto spento
        (f'P4{n}{i}', BP4, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER2, 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '0', 'STRATA_EP_SPLIT_PREFILL': '1'}) for i, n in (
            (1, 'ep2'),
        )
    ],
    'FP5': [   # schermo sulla 2080 Ti (margini come prima: la VRAM libera e' letta col desktop gia' dentro), 3060 senza desktop: due server (salto + righe q8_1), un server, divisione a strati
        (f'P5{n}{i}', BP4, '20', sch, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, sch, e in (
            (1, 'rif', DUE, INSIEME),
            (1, 'fus', DUE, {**PEER, '_args': ['--peer-device', '1', '--peer-reserve-mib', '3000'], 'STRATA_PEER_FUSED': '1'}),
            (1, 'stg', TRE, {**PEER, '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,400'], 'STRATA_PEER_FUSED': '1',
                             'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1'}),
            (2, 'stg', TRE, {**PEER, '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,400'], 'STRATA_PEER_FUSED': '1',
                             'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1'}),
            (2, 'rif', DUE, INSIEME),
        )
    ],
    'FP6': [   # lettura del prompt sul secondo server (3060, riser, senza desktop), due server con salto e stage
        (f'P6{n}{i}', BP6, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'off', {'STRATA_PEER2_PREFILL': '0'}),
            (1, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
            (1, 'r6', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1', 'STRATA_PEER2_PREFILL_ROW_US': '6'}),
        )
    ],
    'FP7': [   # lettura del prompt sul secondo server a ciclo chiuso (3060, riser, senza desktop), due server con salto e stage
        (f'P7{n}{i}', BP7, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'off', {'STRATA_PEER2_PREFILL': '0'}),
            (1, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
            (2, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
        )
    ],
    'FP8': [   # lettura del prompt sul secondo server a ciclo chiuso (3060, riser, senza desktop), due server con salto e stage
        (f'P8{n}{i}', BP8, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'off', {'STRATA_PEER2_PREFILL': '0'}),
            (1, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
            (2, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
        )
    ],
    'FP9': [   # lettura del prompt sul secondo server a ciclo chiuso (3060, riser, senza desktop), due server con salto e stage
        (f'P9{n}{i}', BP9, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'off', {'STRATA_PEER2_PREFILL': '0'}),
            (1, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
            (2, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
        )
    ],
    'FP10': [   # lettura del prompt sul secondo server a ciclo chiuso (3060, riser, senza desktop), due server con salto e stage
        (f'PA{n}{i}', BP10, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'off', {'STRATA_PEER2_PREFILL': '0'}),
            (1, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
            (2, 'on', {'STRATA_PEER2_PREFILL': '1', 'STRATA_PREFILL_TIMING': '1'}),
        )
    ],
    'FP10B': [   # prova pulita: registro dei tempi separato dalla 3060 accesa; (3060, riser, senza desktop), due server con salto e stage
        (f'PB{n}{i}', BP10, '20', TRE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **PEER,
                                                 '_args': ['--peer-device', '1,2', '--peer-reserve-mib', '3000,1000'], 'STRATA_PEER_FUSED': '1',
                                                 'STRATA_PEER2_FUSED': '1', 'STRATA_PEER2_SKIP': '1', 'STRATA_PEER2_STAGE': '1', **e}) for i, n, e in (
            (1, 'tim', {'STRATA_PEER2_PREFILL': '0', 'STRATA_PREFILL_TIMING': '1'}),   # il registro dei tempi da solo, con la 3060 spenta
            (1, 'on', {'STRATA_PEER2_PREFILL': '1'}),                                  # accesa senza registro
            (2, 'on', {'STRATA_PEER2_PREFILL': '1'}),
            (2, 'off', {'STRATA_PEER2_PREFILL': '0'}),
        )
    ],
    'F26': [   # variabili bit-identiche mai provate su Turing, una per volta: banco completo, due corse
        (f'T{n}{i}', B3FF, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'griglia', {'STRATA_IQ_STAGE_GRID_MMVQ': '1'}), (1, 'swiglu', {'STRATA_GU_SWIGLU': '1'}),
            (2, 'rif', {}), (1, 'kq', {'STRATA_KQ_SPLIT': '1'}), (1, 'tsum', {'STRATA_TSUM': '1'}), (3, 'rif', {}),
        )
    ],
    'FL1': [   # PR #4876: la ricorrenza GDN del prompt sui tensor core della 2080 Ti (STRATA_GDN_TC=2, piano a un buffer da 62.480 B).
               # Il riferimento non imposta STRATA_GDN_TC (su Windows il server non lo accende): =2 accende il tc anche sulla 3080 Ti (piano split, come =1)
        (f'G{n}{i}', BGDN, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, e in (
            (1, 'rif', {}), (1, 'tc2', {'STRATA_GDN_TC': '2'}), (2, 'rif', {}), (2, 'tc2', {'STRATA_GDN_TC': '2'}), (3, 'rif', {}),
        )
    ],
    'FK0': [   # testo identico a cache fissa: riferimento e leve con --adapt-swaps 0, una corsa su 4K e 32K; si confrontano i raw
        ('Krif0', BREF, '20', DUE, 700, 384, {'_targets': '4096,32768', '_corse': '1', **TUTTE, **CACHE_FISSA}),
        ('Klev0', BLEV, '20', DUE, 700, 384, {'_targets': '4096,32768', '_corse': '1', **TUTTE, **CACHE_FISSA, **LEVE}),
    ],
    'FK1': [   # banco completo alternato: riferimento, leve, riferimento, leve, riferimento
        (f'K{n}{i}', b, '20', DUE, 700, 384, {'_targets': PIENO, '_corse': '2', **TUTTE, **TEMPI, **e}) for i, n, b, e in (
            (1, 'rif', BREF, {}), (1, 'lev', BLEV, LEVE), (2, 'rif', BREF, {}), (2, 'lev', BLEV, LEVE), (3, 'rif', BREF, {}),
        )
    ],
    'FK3': [   # una copia H2D nel peer (STRATA_PEER_ONE_COPY) contro due, come FEP1: stamp sul flusso del peer, contesto lungo, coppie alternate
        (f'V{n}{i}', BLEV, '20', DUE, 700, 384, {'_lungo': True, **TUTTE, **TEMPI, **PEER, **STAMP, **e}) for i, n, e in (
            (1, 'two', {}), (1, 'one', ONE), (2, 'two', {}), (2, 'one', ONE),
        )
    ],
    'F6': [(f'f20_{n}', B0271, '20', '0,1,2', 700, 384, freddi(n)) for n in (1000, 2000, 4000)] +
          [('p20_senzaprefisso', B0271, '20', DUE, 700, 384, {'_togli': ['--prompt-cache-file']})],
}


def log(m):
    r = f'{time.strftime("%d/%m %H:%M:%S")} {m}'
    print(r, flush=True)
    with open(QUI / 'coda.log', 'a', encoding='utf-8') as f:
        f.write(r + '\n')


def ambiente():
    q = ("$o=@{}; foreach($n in 'CGControl','JumpConnect','dwm'){$p=Get-Process $n -ErrorAction SilentlyContinue;"
         "$o[$n]=[math]::Round(($p|Measure-Object CPU -Sum).Sum,1)};"
         # Win32_VideoController resta indietro dopo un cambio di risoluzione: si legge il desktop (01/11)
         "Add-Type 'using System;using System.Runtime.InteropServices;public class G{[DllImport(\"user32.dll\")]public static extern IntPtr GetDC(IntPtr h);"
         "[DllImport(\"gdi32.dll\")]public static extern int GetDeviceCaps(IntPtr d,int i);[DllImport(\"user32.dll\")]public static extern bool SetProcessDPIAware();}';"
         "[G]::SetProcessDPIAware()|Out-Null;$d=[G]::GetDC([IntPtr]::Zero);"
         "$o['schermo']=\"$([G]::GetDeviceCaps($d,118))x$([G]::GetDeviceCaps($d,117))\";"
         "$o|ConvertTo-Json -Compress")
    return subprocess.run(['powershell', '-NoProfile', '-Command', q], capture_output=True, text=True).stdout.strip()


def ferma():
    subprocess.run(['taskkill', '/F', '/IM', 'strata.exe'], capture_output=True)
    subprocess.run(['taskkill', '/F', '/IM', 'strata-vision.exe'], capture_output=True)


def braccio(nome, build, split, schede, r0, r1, env):
    out = QUI / 'corse' / nome
    if (out / 'FATTO').exists():
        log(f'{nome}: gia fatto, salto')
        return
    out.mkdir(parents=True, exist_ok=True)
    c = json.loads(CFG.read_text(encoding='utf-8-sig'))
    a = c['args']
    a[a.index('--layer-split') + 1] = split
    a[a.index('--vram-reserve-mib') + 1] = str(r0)
    a[a.index('--vram-reserve-later-mib') + 1] = str(r1)
    a[a.index('--prompt-cache-file') + 1] = str(out / 'prefix.bin')
    c['exe'] = str(build / 'strata.exe')
    c['vision']['exe'] = str(build / 'strata-vision.exe')
    c['log'] = str(out / 'engine.log')
    c['env'].update({'CUDA_DEVICE_ORDER': 'PCI_BUS_ID', 'CUDA_VISIBLE_DEVICES': schede, 'STRATA_ROUTE_PRIOR': '0'})
    env = dict(env)
    bersagli = env.pop('_targets', '4096,32768')
    corse = env.pop('_corse', '3')
    lungo = env.pop('_lungo', False)
    prefisso = env.pop('_prefisso', None)
    if prefisso:
        (QUI / 'prefissi' / prefisso).mkdir(parents=True, exist_ok=True)
        a[a.index('--prompt-cache-file') + 1] = str(QUI / 'prefissi' / prefisso / 'prefix.bin')
    if env.pop('_visione', False):
        c['vision'].update({'gpu': True, 'cuda_device': 1})   # numerazione di nvidia-smi: 1 = 3060
    a += ['--ple-io', 'direct'] + env.pop('_args', [])   # sempre SSD: la scelta automatica cambiava tra una corsa e l'altra
    for k in env.pop('_togli', []):
        i = a.index(k)
        del a[i:i + 2]
    for k in env.pop('_togli1', []):
        a.remove(k)
    for k, v in env.items():
        if v is None:
            c['env'].pop(k, None)
        else:
            c['env'][k] = v
    (out / 'config.json').write_text(json.dumps(c, indent=1), encoding='utf-8')
    (out / 'ambiente.txt').write_text(f'inizio {time.strftime("%H:%M")} {ambiente()}\n', encoding='utf-8')
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, b'CODA-NOTTE')
            os.close(fd)
            break
        except FileExistsError:
            time.sleep(2)
    sonda = subprocess.Popen(['nvidia-smi', '--query-gpu=timestamp,index,memory.used,utilization.gpu,power.draw,temperature.gpu',
                              '--format=csv,noheader', '-l', '5', '-f', str(out / 'schede.csv')],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    riser = subprocess.Popen(['nvidia-smi', 'dmon', '-i', '1', '-s', 't', '-d', '2', '-o', 'T', '-f', str(out / 'riser.csv')],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # traffico sul riser della 3060
    slog = open(out / 'server.log', 'w', encoding='utf-8')
    p = subprocess.Popen([str(PY), str(build / 'source/serve/server.py'), '--engine', 'strata', '--config', str(out / 'config.json'),
                          '--host', '127.0.0.1', '--port', '8105'], stdout=slog, stderr=subprocess.STDOUT)
    esito = 'fallito'
    try:
        t0 = time.time()
        while True:
            try:
                urllib.request.urlopen('http://127.0.0.1:8105/v1/models', timeout=5)
                break
            except Exception:
                if p.poll() is not None:
                    raise RuntimeError('server uscito')
                if time.time() - t0 > 900:
                    raise RuntimeError('avvio oltre 15 min')
                time.sleep(5)
        log(f'{nome}: pronto in {time.time() - t0:.0f} s')
        cmd = [str(PY), str(BENCH), '--root', str(build / 'source'), '--pack', r'D:\ds4_work\strata\Strata-data\packs\iq3_xxs',
               '--url', 'http://127.0.0.1:8105', '--out', str(out), '--targets', bersagli, '--runs', corse]
        if lungo:
            cmd = [str(PY), str(QUI / 'banco_lungo.py'), '--out', str(out), '--base', str(QUI / 'corse/Z20tutte_a/tokens-128000-run-1-request.json')]
        r = subprocess.run(cmd,
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3000)
        (out / 'banco.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
        esito = f'finito rc={r.returncode}'
    except Exception as e:
        esito = f'fallito: {e}'
    finally:
        with open(out / 'ambiente.txt', 'a', encoding='utf-8') as f:
            f.write(f'fine {time.strftime("%H:%M")} {ambiente()}\n')
        p.terminate()
        time.sleep(5)
        ferma()
        sonda.terminate()
        riser.terminate()
        slog.close()
        LOCK.unlink(missing_ok=True)
        for f in out.glob('prefix.bin*'):
            f.unlink(missing_ok=True)
        time.sleep(10)
    log(f'{nome}: {esito}')
    if esito.startswith('finito'):
        (out / 'FATTO').write_text(esito, encoding='utf-8')


for fase in sys.argv[1:]:
    log(f'--- fase {fase}')
    for b in FASI[fase]:
        braccio(*b)
log('coda finita')
