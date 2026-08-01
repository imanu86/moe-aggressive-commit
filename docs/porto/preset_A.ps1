# PRESET DEL BRACCIO A — bisezione da una configurazione che COMPLETA.
#
# STORIA, perche' non si ripeta:
#   run 1  preset g73_open.env.ps1 intero          COMPLETATO (0,22 t/s, 10 token)
#   run 2  preset ricopiato da ledger:12945        APPESO nel wrap dell'arena, fase `down`
#   run 3  stesso preset, da NVMe invece che SATA  APPESO allo stesso punto
#
# Il ledger:12945 e' di una sezione VECCHIA, scritta per un altro binario. Applicarlo
# in blocco a bin_codex4 (31/7) appende il wrap. Sostituire una configurazione che
# funziona con una "piu' giusta" presa altrove e' costato due run.
#
# METODO: si parte da cio' che COMPLETA e si cambia UNA variabile per volta.
#   passo 1 (questo file): g73_open MENO le due leve che il ledger documenta come dannose
#           - DS4_G73_OPEN da 1 a 0      ledger 24/7: 0,62 -> 4,85 t/s, e' l'8x
#           - PAGEABLE_OVERFLOW_GB via   non e' nelle configurazioni che rendono
#   Tutto il resto resta IDENTICO al run che ha completato.

# --- arena host pinnata ---
$env:DS4_CUDA_STREAM_RESERVE_MB                = '1024'
$env:DS4_CUDA_DYNAMIC_ARENA_GB                 = '30'
$env:DS4_CUDA_ARENA_WRAP_TRUST_WORKER_CHECKSUM = '1'
$env:DS4_CUDA_ARENA_WRAP_SCHEDULE              = 'source-parts'
$env:DS4_CUDA_ARENA_WRAP_UNLOCK_SOURCE_RANGES  = '1'
$env:DS4_CUDA_ARENA_WRAP_UNLOCK_WAVE_GIB       = '4'
$env:DS4_CUDA_NO_Q8_F16_CACHE                  = '1'
$env:DS4_CUDA_EMBED_ROW_STAGING                = '1'
$env:DS4_REAP_PREFETCH_THREADS                 = '8'

# --- observer del prefill e composizione dei tier ---
$env:DS4_CUDA_PREFILL_MASS_OBSERVE       = '1'
$env:DS4_CUDA_PREFILL_MASS_WRAP          = '1'
$env:DS4_CUDA_PREFILL_TIER_COMPOSE       = '1'
$env:DS4_CUDA_PREFILL_TIER_ROUTER        = 'open'
$env:DS4_CUDA_PREFILL_TIER_RESERVE_SLOTS = '128'

# --- cache esperti in VRAM ---
$env:DS4_CUDA_STREAMING_EXPERT_CACHE_N          = '320'
$env:DS4_CUDA_STREAMING_EXPERT_CACHE_RESERVE_GB = '0.125'
$env:DS4_CUDA_MOE_CACHE_POLICY                  = 'lru'

# --- route MoE ---
$env:DS4_CUDA_MOE_GPU_RESIDENT_ROUTES   = '1'
$env:DS4_CUDA_MOE_ROUTE_NO_DEFAULT_SYNC = '1'

# --- tiering / promozione ---
$env:DS4_EXPERT_TIERING                 = 'enforce'
$env:DS4_EXPERT_TIER_POLICY             = 'mass-lfru'
$env:DS4_EXPERT_TIER_CLOCK_CALLS        = '430'
$env:DS4_EXPERT_TIER_REPLACEMENT_BUDGET = '32'
$env:DS4_EXPERT_TIER_MIN_FREQUENCY      = '3'
$env:DS4_EXPERT_TIER_HYSTERESIS         = '1.25'
$env:DS4_G133_TIER                      = '1'
$env:DS4_G133_KNOCK_X                   = '3'
$env:DS4_G133_ROTATOR_IO_TIMEOUT_S      = '0.05'

# --- LA VARIABILE DEL PASSO 1 ---
$env:DS4_G73_OPEN = '0'    # era 1. Ledger 24/7: a 0 e' 8x piu' veloce.

# --- le due leve PROMOSSE (atlante) ---
$env:DS4_EXPERT_TIER_ADMIT_KNOCKS_SSD     = '3'   # +4,0%, testo byte-identico
$env:DS4_CUDA_TRANSIENT_DEADLINE_ADAPTIVE = '1'   # 12 esaurimenti -> 0, costo zero

# --- TOLTO rispetto al run che ha completato, e perche' ---
#   DS4_G73_PAGEABLE_OVERFLOW_GB=14   non compare in nessuna configurazione che rende
#
# --- NON aggiunto, anche se sta in ledger:12945: appende il wrap su questo binario ---
#   KV_STAGED_RING, MOE_SPLIT_FUSED, STREAM_FROM_RAM_MASKED_BUDGET_GB,
#   STREAM_HOT_RESERVE_MB, RELEASE_PREFILL_SCRATCH

# --- PASSO 2 (1/8 17:15): rimetto la maschera, unica variabile aggiunta ---
# Il log dice: 72,56 GiB di esperti esclusi dalla startup cache, quindi in VRAM ci
# sta il backbone (~8,2 GiB). Restano 1,02 GB al dimensionamento -> 135 slot.
# Il riferimento ne aveva ~1,7 -> 253 slot. Questa variabile maschera 2 GiB di pesi
# perche' arrivino dalla RAM invece che stare in VRAM: e' esattamente il buco.
$env:DS4_CUDA_STREAM_FROM_RAM_MASKED_BUDGET_GB = '2'

# --- PASSO 3 (1/8 18:45): il prefill chunk, unica variabile aggiunta ---
# Trovato leggendo il codice, non a tentativi. Il nostro log dice:
#   context buffers 329.92 MiB (ctx=8000, backend=cuda, prefill_chunk=2048, ...)
# Il default a ctx 8000 e' 2048; lo script di campagna che ha prodotto il
# riferimento da 253 slot usa 256. I buffer di attenzione batch costano
# 944,5 MiB a chunk 2048 contro 118,06 a chunk 256: 826,4 MiB di differenza,
# contro i 790,55 che mancano per arrivare a capacity 253.
# RITIRATA la mia ipotesi precedente su EXPERT_CACHE_GROW: il commento a
# ds4_cuda.cu:40814 e' reale ma spiega il MOMENTO della misura, non la
# GRANDEZZA del buco.
$env:DS4_METAL_PREFILL_CHUNK = '256'
