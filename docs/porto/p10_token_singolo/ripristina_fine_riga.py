"""P10 cella 2 - rimette i fine-riga originali sulle righe NON toccate.

I tre file del motore hanno fine-riga MISTI (qualche riga con solo LF in mezzo a
migliaia di righe CRLF). L'editor usato in questa cella normalizza tutto a CRLF, e il
diff si riempie di righe che sembrano cambiate e non lo sono. Qui si riallineano base e
versione corrente per contenuto (difflib) e, su ogni riga rimasta uguale, si ripristina
il fine-riga della base. Le righe aggiunte restano come sono.

Non cambia nessun byte di codice: solo i terminatori di riga di righe invariate.
"""
import difflib
import sys
from pathlib import Path

COPPIE = [
    (r"D:\ds4_work\p8_work\prove\p10_c2_base\ggml-backend.cpp",
     r"D:\ds4_work\p8_work\source\ggml\src\ggml-backend.cpp"),
    (r"D:\ds4_work\p8_work\prove\p10_c2_base\ggml-cuda.cu",
     r"D:\ds4_work\p8_work\source\ggml\src\ggml-cuda\ggml-cuda.cu"),
    (r"D:\ds4_work\p8_work\prove\p10_c2_base\llama-context.cpp",
     r"D:\ds4_work\p8_work\source\src\llama-context.cpp"),
]


def spezza(dati):
    """[(contenuto_senza_terminatore, terminatore)] conservando i fine-riga."""
    fuori = []
    inizio = 0
    i = 0
    n = len(dati)
    while i < n:
        if dati[i:i + 1] == b"\n":
            if i > inizio and dati[i - 1:i] == b"\r":
                fuori.append((dati[inizio:i - 1], b"\r\n"))
            else:
                fuori.append((dati[inizio:i], b"\n"))
            inizio = i + 1
        i += 1
    if inizio < n:
        fuori.append((dati[inizio:], b""))
    return fuori


def main():
    for base_p, ora_p in COPPIE:
        base = spezza(Path(base_p).read_bytes())
        ora = spezza(Path(ora_p).read_bytes())
        a = [x[0] for x in base]
        b = [x[0] for x in ora]
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        cambi = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                continue
            for k in range(i2 - i1):
                if ora[j1 + k][1] != base[i1 + k][1] and ora[j1 + k][1] and base[i1 + k][1]:
                    ora[j1 + k] = (ora[j1 + k][0], base[i1 + k][1])
                    cambi += 1
        Path(ora_p).write_bytes(b"".join(c + t for c, t in ora))
        print("%-58s righe riallineate: %d" % (Path(ora_p).name, cambi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
