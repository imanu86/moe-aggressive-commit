$ErrorActionPreference = 'Stop'
$ENC = [Text.Encoding]::GetEncoding(28591)   # ISO-8859-1: round-trip byte per byte

function RT($p) { return $ENC.GetString([IO.File]::ReadAllBytes($p)) }
function WT($p, $s) { [IO.File]::WriteAllBytes($p, $ENC.GetBytes($s)) }

function SplitLines($s) {
    $out = New-Object System.Collections.ArrayList
    $i = 0; $start = 0
    while ($i -lt $s.Length) {
        $c = $s[$i]
        if ($c -eq "`n") { [void]$out.Add($s.Substring($start, $i - $start + 1)); $i++; $start = $i; continue }
        if ($c -eq "`r") {
            if (($i + 1) -lt $s.Length -and $s[$i+1] -eq "`n") { [void]$out.Add($s.Substring($start, $i - $start + 2)); $i += 2 }
            else { [void]$out.Add($s.Substring($start, $i - $start + 1)); $i++ }
            $start = $i; continue
        }
        $i++
    }
    if ($start -lt $s.Length) { [void]$out.Add($s.Substring($start)) }
    return ,$out
}
function Bd($chunk) {
    if ($chunk.EndsWith("`r`n")) { return $chunk.Substring(0, $chunk.Length - 2) }
    if ($chunk.EndsWith("`n") -or $chunk.EndsWith("`r")) { return $chunk.Substring(0, $chunk.Length - 1) }
    return $chunk
}
function Tm($chunk) {
    if ($chunk.EndsWith("`r`n")) { return "`r`n" }
    if ($chunk.EndsWith("`n")) { return "`n" }
    if ($chunk.EndsWith("`r")) { return "`r" }
    return ""
}
function FindAnchor($lines, $anchor) {
    $hits = @()
    for ($i = 0; $i -lt $lines.Count; $i++) { if ((Bd $lines[$i]) -eq $anchor) { $hits += $i } }
    if ($hits.Count -ne 1) { throw "ANCORA NON UNICA ($($hits.Count) occorrenze): |$anchor|" }
    return $hits[0]
}
# Inserisce $block dopo la riga (ancora + offset). Ogni riga nuova eredita la
# terminazione della riga che la ospita. Verifica la riga successiva attesa.
function InsAfter($lines, $anchor, $offset, $expectNext, $block) {
    $i = FindAnchor $lines $anchor
    $pos = $i + $offset
    if ($pos -lt 0 -or $pos -ge $lines.Count) { throw "OFFSET FUORI FILE per |$anchor|" }
    $next = ''
    if (($pos + 1) -lt $lines.Count) { $next = Bd $lines[$pos + 1] }
    if ($next -ne $expectNext) { throw "RIGA SEGUENTE INATTESA dopo |$anchor|+$offset : attesa |$expectNext| trovata |$next|" }
    $t = Tm $lines[$pos]
    if ($t -eq "") { throw "RIGA OSPITE SENZA TERMINATORE per |$anchor|" }
    $nuove = @()
    foreach ($b in $block) { $nuove += ($b + $t) }
    $lines.InsertRange($pos + 1, [string[]]$nuove)
    return $nuove.Count
}
# Sostituisce la riga (ancora + offset) con una o piu' righe, stesso terminatore.
function RepAt($lines, $anchor, $offset, $expectOld, $block) {
    $i = FindAnchor $lines $anchor
    $pos = $i + $offset
    $old = Bd $lines[$pos]
    if ($old -ne $expectOld) { throw "RIGA DA SOSTITUIRE INATTESA a |$anchor|+$offset : attesa |$expectOld| trovata |$old|" }
    $t = Tm $lines[$pos]
    if ($t -eq "") { throw "RIGA SENZA TERMINATORE per |$anchor|+$offset" }
    $lines.RemoveAt($pos)
    $nuove = @()
    foreach ($b in $block) { $nuove += ($b + $t) }
    $lines.InsertRange($pos, [string[]]$nuove)
    return $nuove.Count
}

$root = 'D:\llama-subtract\ggml\src\ggml-cuda'
$fcu  = Join-Path $root 'cache-esperti.cu'
$fcuh = Join-Path $root 'cache-esperti.cuh'

# ======================================================================= .cuh
$L = SplitLines (RT $fcuh)
$n0 = $L.Count
[void](InsAfter $L '                              //           sfratti, sorpassate, id fuori range' 0 '' @(
'                              //           [7] rifiutate_pressione (v0.1)',
'',
'    // v0.1 -- LA DISCIPLINA DELLE PRENOTAZIONI. `to_budget` e'' il tetto di',
'    // prenotazioni speculative per TOKEN (0 = illimitato, cioe'' il v0, che ne',
'    // faceva ~72 per token contro ~16 miss veri). `to_stato` e'' [2]: [0]',
'    // ultimo strato visto, [1] speso nel token corrente. Sta sul DEVICE',
'    // perche'' deve poter cambiare per ciclo: cio'' che e'' per valore si',
'    // congela alla cattura del grafo, e un tetto per token non puo''.',
'    int        to_budget;',
'    int32_t *  to_stato;'
))
WT $fcuh (-join $L)
"cuh: righe $n0 -> $($L.Count)"

# ======================================================================== .cu
$L = SplitLines (RT $fcu)
$n0 = $L.Count

# --- 1. il campo pf_legacy nel runtime
[void](InsAfter $L '    int          pf_dev = 0;' 0 '    const void * pf_bg[CACHE_ESPERTI_MAX_STRATI] = {};' @(
'    // v0.1 -- IL CONSUMATORE LEGACY DEL PREDITTORE',
'    // (LLAMA_CACHE_ESPERTI_PF_LEGACY, difetto 1 = il cammino di oggi). Con',
'    // W>=1 il nodo `cache_pf-` nasce, e da li'' partono DUE cose: kern_prenota',
'    // sullo stream di calcolo e il thread di servizio che ne copia i byte.',
'    // E'' l''apparato che il banco del 17/8 ha pagato -47,3% (A -> A''). A 0 il',
'    // predittore resta VIVO e il consumatore sparisce: e'' il ramo che il',
'    // trasporto online forza, ed e'' anche il braccio di controllo A''''',
'    // (trasporto spento, legacy soppresso).',
'    int          pf_legacy = 1;'
))

# --- 2. la leva del budget, dentro il blocco TRASPORTO_ONLINE
[void](InsAfter $L '            runtime->cache.to_attivo = d > 0 ? (d < 8 ? d : 8) : 0;' 0 '            if (runtime->cache.to_attivo) {' @(
'            // v0.1 -- IL TETTO PER TOKEN. A VALORE (atoi), come la leva madre.',
'            // Difetto 24 = ~1,5x i ~16 miss veri per token; 0 = ILLIMITATO,',
'            // cioe'' il v0, che su ~1.075 token ha fatto 77.957 prenotazioni e',
'            // 74.372 sfratti (95,4% del prenotato era uno sfratto).',
'            const char * b = getenv("LLAMA_TRASPORTO_ONLINE_BUDGET");',
'            const int bt = (b && *b) ? atoi(b) : 24;',
'            runtime->cache.to_budget = bt > 0 ? bt : 0;'
))

# --- 3. la leva PF_LEGACY, subito dopo il blocco TRASPORTO_ONLINE
[void](InsAfter $L '                            "nel grafo e nessun id predetto arriva al trasporto");' 4 '        {' @(
'        {',
'            // v0.1 -- IL CONSUMATORE LEGACY, A VALORE (atoi), difetto 1 = il',
'            // cammino di oggi. Il trasporto online lo FORZA a 0: due',
'            // consumatori sullo stesso predittore sono due trasporti, e il',
'            // banco ha gia'' misurato quanto costa quello vecchio.',
'            const char * v = getenv("LLAMA_CACHE_ESPERTI_PF_LEGACY");',
'            runtime->pf_legacy = (v && *v) ? (atoi(v) != 0 ? 1 : 0) : 1;',
'            if (runtime->cache.to_attivo > 0 && runtime->pf_legacy) {',
'                runtime->pf_legacy = 0;',
'                fprintf(stderr, "cache-esperti: TRASPORTO ONLINE: prefetch LEGACY forzato SPENTO "',
'                                "(kern_prenota e thread di servizio) -- il trasporto e'' l''unico consumatore\n");',
'            }',
'        }'
))

# --- 4. to_stato: allocazione, azzeramento, log, free
[void](InsAfter $L '        cudaMalloc(&runtime->cache.to_cont,       TO_CONT * sizeof(uint64_t)) == cudaSuccess &&' 0 "        // priorita' BASSA: sullo stream del trasporto non gira nessun kernel di" @(
'        cudaMalloc(&runtime->cache.to_stato,      2 * sizeof(int32_t)) == cudaSuccess &&'
))
[void](InsAfter $L '    cudaMemset(runtime->cache.to_cont,       0, TO_CONT * sizeof(uint64_t));' 0 '    cudaEventCreate(&runtime->to_ev_a);' @(
'    cudaMemset(runtime->cache.to_stato,      0, 2 * sizeof(int32_t));'
))
[void](InsAfter $L '            TO_ANELLO_N, priorita_bassa);' 0 '}' @(
'    fprintf(stderr, "cache-esperti: TRASPORTO ONLINE v0.1: budget=%d prenotazioni/token "',
'                    "(0 = illimitato), sfratto speculativo ammesso SOLO su slot libero o "',
'                    "freddo -- mai un residente vivo\n", runtime->cache.to_budget);'
))
[void](InsAfter $L '    if (runtime->cache.to_cont)       { cudaFree(runtime->cache.to_cont);        runtime->cache.to_cont = nullptr; }' 0 '    if (runtime->cache.to_atterrato)  { cudaFree(runtime->cache.to_atterrato);   runtime->cache.to_atterrato = nullptr; }' @(
'    if (runtime->cache.to_stato)      { cudaFree(runtime->cache.to_stato);       runtime->cache.to_stato = nullptr; }'
))

# --- 5. i due helper + la firma di cache_vittima
[void](RepAt $L '__device__ static int cache_vittima(cache_esperti & c, bool prefetch) {' 0 '__device__ static int cache_vittima(cache_esperti & c, bool prefetch) {' @(
'// v0.1 -- IL CRITERIO DI FREDDEZZA, e non e'' un allocatore nuovo: sono',
'// ESATTAMENTE i campi che la macchina di sfratto gia'' mantiene.',
'//',
'//   libero          chi[slot] < 0',
'//   orfano          dove[] non punta piu'' qui: non e'' residente per nessuno',
'//   mai usato       usato[slot] == 0, la seconda chance dell''orologio',
'//   freddo per eta'' con lru=1, non toccato da n_slot battiti -- un giro intero',
'//                   della cache in unita'' di domanda (~258 attivazioni per',
'//                   token su ~512 slot: circa due token, che e'' l''orizzonte',
'//                   di residenza misurato). La soglia si auto-calibra sulla',
'//                   capienza, quindi NON introduce una leva nuova.',
'//',
'// Tutto il resto e'' un RESIDENTE VIVO, e una prenotazione SPECULATIVA non lo',
'// puo'' sfrattare: e'' il canale da cui il v0 ha perso (74.372 sfratti su 77.957',
'// prenotazioni, 95,4%) ed e'' lo stesso da cui PF_TOP perse i colpi il 13/8.',
'__device__ static bool cache_slot_freddo(const cache_esperti & c, int slot) {',
'    const int32_t cm = c.chi[slot];',
'    if (cm < 0) return true;                                     // libero',
'    if (cm & CACHE_ESPERTI_TRANSITO) return false;               // byte in arrivo',
'    const int indice = ((((cm >> 16) & 0x3f) << 8) | (cm & 0xff));',
'    if (c.dove[indice] != slot) return true;                     // orfano',
'    if (!c.usato[slot]) return true;                             // mai usato',
'    if (c.lru && c.epoca && c.ultimo &&',
'        c.ultimo[slot] + (uint64_t) c.n_slot <= *c.epoca) {',
'        return true;                                             // freddo per eta''',
'    }',
'    return false;                                                // residente VIVO',
'}',
'',
'// IL VETO, prima di QUALUNQUE mutazione: la vittima si rifiuta e la mano NON',
'// avanza, quindi il rifiuto e'' un no-op esatto sullo stato della cache. Lo',
'// paga solo chi chiede `fredda`, cioe'' il trasporto online: a `fredda = false`',
'// questa funzione e'' identica lettera per lettera a quella di ieri.',
'__device__ static bool cache_vittima_rifiuta(cache_esperti & c, bool fredda, int vittima) {',
'    if (!fredda || vittima < 0 || cache_slot_freddo(c, vittima)) return false;',
'    if (c.to_cont) c.to_cont[7] += 1;      // rifiutate_pressione',
'    return true;',
'}',
'',
'__device__ static int cache_vittima(cache_esperti & c, bool prefetch, bool fredda = false) {'
))

# --- 6. il veto nei quattro rami di cache_vittima
[void](InsAfter $L '                massa_minima = c.massa[indice];' 4 '        if (vittima >= 0) {' @(
'        // v0.1 -- ANTI-ALLUVIONE: una prenotazione speculativa non sfratta vivi.',
'        if (cache_vittima_rifiuta(c, fredda, vittima)) return -1;',
''
))
[void](InsAfter $L '        if (vittima < 0) vittima = vittima_protetta;' 1 '        if (vittima >= 0) {' @(
'        // v0.1 -- ANTI-ALLUVIONE: una prenotazione speculativa non sfratta vivi.',
'        if (cache_vittima_rifiuta(c, fredda, vittima)) return -1;',
''
))
[void](InsAfter $L '                classe = fase;' 4 '        if (vittima >= 0) {' @(
'        // v0.1 -- ANTI-ALLUVIONE: una prenotazione speculativa non sfratta vivi.',
'        if (cache_vittima_rifiuta(c, fredda, vittima)) return -1;',
''
))
[void](InsAfter $L '            if (!c.usato[mano]) { vittima = mano; break; }' 5 '    if (vittima >= 0) {' @(
'    // v0.1 -- ANTI-ALLUVIONE: una prenotazione speculativa non sfratta vivi.',
'    if (cache_vittima_rifiuta(c, fredda, vittima)) return -1;',
''
))

# --- 7. kern_to_prenota: budget per token + vittima fredda
[void](InsAfter $L '    cache_to_promuovi(c);' 0 '' @(
'',
'    // v0.1 -- IL TETTO PER TOKEN. Il v0 prenotava ~72 slot per token contro',
'    // ~16 miss veri: un''alluvione che sfrattava residenti vivi. Il token si',
'    // riconosce dal RITORNO dello strato (dentro un forward gli strati',
'    // crescono), e lo stato sta sul DEVICE: il grafo lo rilegge fresco a ogni',
'    // replay, esattamente come i cursori dell''anello. A budget 0 il ramo e''',
'    // inerte e si riproduce la disciplina del v0.',
'    int cap = c.to_attivo;',
'    int speso = 0;',
'    if (c.to_budget > 0 && c.to_stato) {',
'        if (strato <= c.to_stato[0]) c.to_stato[1] = 0;    // token nuovo',
'        c.to_stato[0] = strato;',
'        speso = c.to_stato[1];',
'        const int resto = c.to_budget - speso;',
'        if (resto <= 0) return;                            // budget del token esaurito',
'        if (resto < cap) cap = resto;',
'    }'
))
[void](RepAt $L '    for (int i = 0; i < n_id && m < c.to_attivo; i++) {' 0 '    for (int i = 0; i < n_id && m < c.to_attivo; i++) {' @(
'    for (int i = 0; i < n_id && m < cap; i++) {'
))
[void](RepAt $L '        if (testa + m - conf >= TO_ANELLO_N - 1) break;' 1 '        const int vittima = cache_vittima(c, true);' @(
'        // v0.1: SOLO vittime fredde. Se non ce n''e'' la prenotazione si scarta',
'        // e si conta in `rifiutate_pressione`: meglio nessun anticipo che un',
'        // anticipo pagato con un residente vivo.',
'        const int vittima = cache_vittima(c, true, true);'
))
[void](InsAfter $L '        an[0] = testa + m;' 0 '    }' @(
'        if (c.to_budget > 0 && c.to_stato) c.to_stato[1] = speso + m;'
))

# --- 8. il thread di servizio, sotto cancello
[void](RepAt $L '        runtime->servizio = new std::thread(cache_esperti_servizio, runtime);' 0 '        runtime->servizio = new std::thread(cache_esperti_servizio, runtime);' @(
'        // v0.1 -- IL CONSUMATORE LEGACY, META'' HOST. Il thread nasceva',
'        // INCONDIZIONATO: con W>=1 e'' l''altra meta'' del prefetch legacy',
'        // (kern_prenota pubblica nell''anello, lui copia i byte), ed e'' la',
'        // parte di apparato che il banco del 17/8 ha pagato -47,3% ad A''.',
'        // A PF_LEGACY=0 non nasce: l''UNICO produttore dell''anello e''',
'        // kern_prenota (:4666), che allo stesso cancello non parte piu''.',
'        // Lo `stream_pf` resta creato: lo usa anche il prefetch DEVICE',
'        // (pf_dev, :5854-5858), che non passa da qui. Il ramo DMA invece il',
'        // thread lo ESIGE (e'' la sua macchina a stati), quindi li'' nasce',
'        // comunque: il cancello non tocca una leva che non e'' sua.',
'        if (runtime->pf_legacy || runtime->dma_leva) {',
'            runtime->servizio = new std::thread(cache_esperti_servizio, runtime);',
'        } else {',
'            fprintf(stderr, "cache-esperti: PREFETCH LEGACY SOPPRESSO: niente kern_prenota, "',
'                            "niente thread di servizio (gli id predetti restano, il consumatore no)\n");',
'        }'
))

# --- 9. il gate sul lancio di kern_prenota
[void](InsAfter $L 'void ggml_cuda_cache_esperti_prenota(cache_esperti_runtime * runtime,' 3 '    if (cache_dma_strato_quieto(runtime)) return;' @(
'    // v0.1 -- IL GATE DEL CONSUMATORE LEGACY. Il nodo `cache_pf-` continua a',
'    // nascere e a produrre id (servono al trasporto online), ma da qui non',
'    // parte piu'' niente: questo e'' l''UNICO sito da cui W>=1 innesca',
'    // kern_prenota fuori dal ramo DMA (l''altro, :835, e'' del piano DMA).',
'    if (!runtime->pf_legacy) return;'
))

# --- 10. i due testimoni nuovi nel dump
[void](InsAfter $L '    //                          banda bassa (<10 GiB/s) = submission WDDM.' 0 '    if (runtime->cache.to_attivo > 0) {' @(
'    //   budget              -- v0.1: il tetto di prenotazioni per token',
'    //                          (LLAMA_TRASPORTO_ONLINE_BUDGET, 0 = illimitato).',
'    //   rifiutate_pressione -- v0.1: prenotazioni SCARTATE perche'' l''unica',
'    //                          vittima disponibile era un residente VIVO. Alto',
'    //                          = la cache e'' piena di lavoro utile e non c''e''',
'    //                          spazio per l''anticipo. NON e'' un guasto: e'' il',
'    //                          prezzo che il v0 pagava in sfratti, reso visibile.'
))
[void](RepAt $L '        fprintf(stderr, "cache-esperti: trasporto-online -> d=%d, previsti=%llu, prenotati=%llu, "' 0 '        fprintf(stderr, "cache-esperti: trasporto-online -> d=%d, previsti=%llu, prenotati=%llu, "' @(
'        fprintf(stderr, "cache-esperti: trasporto-online -> d=%d, budget=%d, previsti=%llu, prenotati=%llu, "'
))
[void](RepAt $L '                        "in volo max=%d (tetto %d), confini=%llu, senza basi=%llu, "' 0 '                        "in volo max=%d (tetto %d), confini=%llu, senza basi=%llu, "' @(
'                        "in volo max=%d (tetto %d), confini=%llu, senza basi=%llu, "',
'                        "rifiutate_pressione=%llu, "'
))
[void](RepAt $L '                runtime->cache.to_attivo,' 0 '                runtime->cache.to_attivo,' @(
'                runtime->cache.to_attivo, runtime->cache.to_budget,'
))
[void](InsAfter $L '                (unsigned long long) runtime->to_senza_basi,' 0 '                runtime->to_pinnata ? "pinnata" : "NON VERIFICATA",' @(
'                (unsigned long long) t[7],'
))

WT $fcu (-join $L)
"cu:  righe $n0 -> $($L.Count)"
"OK"
