@echo off
REM ===========================================================================
REM  AVVIA.bat -- lancia DeepSeek-V4-Flash in modo IBRIDO
REM
REM  Modifica solo le variabili qui sotto. Tutto il resto e' gia' tarato sulle
REM  misure del 4-5 agosto e conviene lasciarlo com'e'.
REM ===========================================================================

REM --- LE MANOPOLE ------------------------------------------------------------

REM Contesto e ubatch. Il buffer di calcolo in VRAM cresce con CONTESTO x UBATCH
REM x NUMERO DI SLOT, e la scheda ha 12 GB.
REM
REM CORREZIONE DEL 5/8 SERA -- il vincolo che avevo scritto qui era sbagliato di
REM un fattore quattro. Il server allocava QUATTRO slot paralleli di default,
REM ognuno col suo buffer, su una macchina che serve una richiesta alla volta:
REM
REM   ctx 102400, ub  16, np 4 (com'era)   VRAM 11.920 MiB   liberi   368
REM   ctx 102400, ub  16, np 1             VRAM  9.062 MiB   liberi 3.226
REM   ctx 102400, ub 128, np 1             VRAM 10.510 MiB   liberi 1.778
REM
REM Con np 1 l'ubatch puo' salire da 16 a 128 A CONTESTO PIENO, e il prefill
REM passa a 19,21 t/s (il decode resta 7,99: non dipende dall'ubatch).
REM
REM E il contesto lungo NON costa VRAM: la KV di DSV4 e' compressa, a 102.400
REM occupa 10,75 MiB perche' la finestra e' 256 celle. Costavano solo i buffer.
set CONTESTO=102400
set UBATCH=128
set SLOT=1

REM Porta e indirizzo. 0.0.0.0 = raggiungibile dalla rete locale.
REM Per limitarlo a questo PC soltanto: 127.0.0.1
set PORTA=8080
set INDIRIZZO=0.0.0.0

REM Strumenti per l'agente.
REM   --agent                        tutti, SHELL COMPRESA
REM   --tools read_file,write_file   solo quelli elencati
REM   (vuoto)                        nessuno strumento
REM Gli strumenti costano ~1.570 token di prompt a OGNI turno.
set STRUMENTI=--agent

REM Quanti strati di esperti vanno in memoria mappata (zero-copy).
REM Misurato: con l'ibrido acceso conviene mapparli TUTTI, perche' il prefill
REM li usa sulla GPU e il decode li usa sulla CPU, sugli stessi byte.
REM Per mapparne solo i primi N: blk\.([0-9]^|1[0-3])\. davanti al nome
set MAPPA_TUTTI=1

REM --- FINE DELLE MANOPOLE ----------------------------------------------------

set MODELLO=C:\ds4-models\DS4-0731-IQ2XXS.gguf
set ESEGUIBILE=D:\llama-dspark\build\bin\llama-server.exe
set LOG=D:\ds4_work\llama_run\LLAMA_avvio.log

REM IBRIDO: prefill sulla GPU (batch grande, il PCIe si ammortizza), decode
REM sulla CPU (batch 1, la RAM batte il PCIe). Stessi byte, nessuna copia:
REM cudaHostAlloc restituisce lo stesso indirizzo per host e device.
REM Misurato il 5/8:  ibrido 15,31 t/s di prefill e 6,99 di decode, contro
REM 6,94/6,91 con zero mappati e 15,01/5,95 con tutto sulla GPU.
set LLAMA_MAPPED_IBRIDO=1

REM Soglia di commutazione: batch sotto questo valore va alla CPU.
set LLAMA_MAPPED_IBRIDO_SOGLIA=2

REM reap-loop spento: con il modello interamente residente non serve piu'.
set LLAMA_REAP=0

if "%MAPPA_TUTTI%"=="1" (
  set OT=ffn_(gate^|up^|down^)_exps\.weight=CUDA0_Mapped
) else (
  set OT=blk\.([0-9]^|1[0-3]^)\.ffn_(gate^|up^|down^)_exps\.weight=CUDA0_Mapped,ffn_(gate^|up^|down^)_exps\.weight=CPU
)

echo.
echo   modello    %MODELLO%
echo   contesto   %CONTESTO%   ubatch %UBATCH%   slot %SLOT%
echo   indirizzo  http://%INDIRIZZO%:%PORTA%
echo   strumenti  %STRUMENTI%
echo   ibrido     acceso (soglia %LLAMA_MAPPED_IBRIDO_SOGLIA%)
echo.
echo   Il caricamento richiede circa 80 secondi.
echo   Chiudi questa finestra per fermare il server.
echo.

REM --no-mmap e' OBBLIGATORIO quando si mappa: senza, gli stessi byte stanno
REM due volte in RAM (pagine del file + buffer pinnato) e la macchina annaspa.
"%ESEGUIBILE%" ^
  -m "%MODELLO%" ^
  -c %CONTESTO% ^
  -np %SLOT% ^
  -ngl 99 ^
  -ot "%OT%" ^
  -ub %UBATCH% -b %UBATCH% ^
  --port %PORTA% --host %INDIRIZZO% ^
  --no-warmup --no-mmap --ui --jinja --cache-reuse 256 ^
  %STRUMENTI% ^
  2> "%LOG%"

echo.
echo   Server terminato. Il log e' in %LOG%
pause
