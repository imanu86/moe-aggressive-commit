# Simulatore OFFLINE del tetto di accettazione del lookahead (Fu et al.)
# sul flusso greedy vero, senza toccare il modello.
#
# Pool IDEALE (limite superiore): per ogni token ft, gli (N-1)-grammi che
# seguono OGNI occorrenza di ft nel flusso visto finora (prompt + generato),
# capacita' G per chiave come nel ring di lookahead.cpp. Il pool vero e'
# riempito dalle traiettorie Jacobi, che nel migliore dei casi convergono
# verso il testo futuro: quindi il vero n_accept <= questo tetto.
#
# A ogni passo al token corrente S[t]: si accettano fino a N-1 token extra
# se un n-gramma del pool combacia col futuro vero S[t+1..]. Il passo emette
# sempre 1 + accettati (token0 + verifica), come in lookahead.cpp.
#
# Uso: python sim_lookahead_pool.py tokens.txt W N G
# tokens.txt: un id per riga (uscita di llama-tokenize), prompt incluso.

import sys
from collections import defaultdict, deque

def simula(S, W, N, G, n_prompt):
    # pool[ft] = deque di tuple (N-1 token), capacita' G, dal flusso gia' visto
    pool = defaultdict(lambda: deque(maxlen=G))

    def alimenta_fino(t_escluso):
        # inserisce gli n-grammi che INIZIANO fino a t_escluso-1 (serve l'intero
        # n-gramma nel passato: inizio i, corpo i+1..i+N-1 tutti < t_escluso)
        while alimenta_fino.next_i + N - 1 < t_escluso:
            i = alimenta_fino.next_i
            ft = S[i]
            corpo = tuple(S[i+1:i+N])
            if corpo not in pool[ft]:
                pool[ft].append(corpo)
            alimenta_fino.next_i += 1
    alimenta_fino.next_i = 0

    t = n_prompt          # primo token generato
    passi = 0
    accettati_tot = 0
    emessi = 0
    dist = defaultdict(int)
    while t < len(S) - 1:
        alimenta_fino(t + 1)   # il pool conosce tutto fino al token corrente incluso
        ft = S[t]
        migliore = 0
        for corpo in pool[ft]:
            k = 0
            while k < N - 1 and t + 1 + k < len(S) and corpo[k] == S[t + 1 + k]:
                k += 1
            migliore = max(migliore, k)
        # il passo emette token0 (t+1 in realta' e' il sample di questo passo...
        # contabilita' identica a lookahead.cpp: 1 emesso + 'migliore' accettati)
        passi += 1
        emessi += 1 + migliore
        accettati_tot += migliore
        dist[migliore] += 1
        t += 1 + migliore

    return passi, emessi, accettati_tot, dist

def main():
    path, W, N, G = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    n_prompt = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    S = [int(r) for r in open(path, encoding='utf-8').read().split() if r.strip().lstrip('-').isdigit()]
    passi, emessi, acc, dist = simula(S, W, N, G, n_prompt)
    print(f"token totali={len(S)} (prompt={n_prompt}, generati={len(S)-n_prompt})")
    print(f"W={W} N={N} G={G}")
    print(f"passi={passi}  emessi={emessi}  accettati={acc}")
    print(f"TOKEN/PASSO (tetto) = {emessi/passi:.3f}")
    print(f"distribuzione accettati per passo: {dict(sorted(dist.items()))}")

if __name__ == '__main__':
    main()
