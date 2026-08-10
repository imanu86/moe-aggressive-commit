"""
CANTIERE TESTA — passo 2: l'adapter non lineare contro la ridge lineare,
sugli STESSI dati. Zero macchina (GPU locale, secondi).

Domanda: a n=1.600 il collo e' il MODELLO (lineare) o i DATI?
  - MLP batte la ridge  -> serve nonlinearita', e piu' dati la aiutano: la
                           raccolta grande e' giustificata due volte;
  - MLP non batte       -> il collo sono i DATI, e la raccolta e' l'unica cosa
                           che conta (niente da guadagnare a complicare).

Architettura (piano, senza stato): h(t) -> adapter -> stato predetto di t+1
                                        -> output_norm + lm_head CONGELATE
                                        -> logit -> argmax = token t+2

DISTILLAZIONE: il bersaglio non e' solo l'argmax ma la DISTRIBUZIONE del
modello (top-k dei suoi logit), che porta molta piu' informazione per token.
Qui la usiamo come perdita ausiliaria (KL sui top-k) accanto alla ricostruzione
dello stato.
"""

import os, sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, r'D:\llama-dspark\gguf-py')
import gguf

MODELLO = r'C:\ds4-models\DS4-0731-IQ2XXS.gguf'
COPPIE = r'D:\ds4_work\dump_prosa\coppie_h42.npz'      # la prosa: il codice e' boilerplate
TOPK = 32
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'


def testa_congelata():
    r = gguf.GGUFReader(MODELLO, 'r')
    out = {}
    for t in r.tensors:
        if t.name in ('output.weight', 'output_norm.weight'):
            a = np.array(t.data)
            if t.tensor_type != gguf.GGMLQuantizationType.F32:
                a = gguf.quants.dequantize(t.data, t.tensor_type)
            out[t.name] = a.astype(np.float32).reshape(tuple(int(x) for x in reversed(t.shape)))
    return out['output.weight'], out['output_norm.weight'].reshape(-1)


print('CANTIERE TESTA — adapter contro ridge, stessi dati\n')
W, g = testa_congelata()
W_t = torch.from_numpy(W).to(DEV)
g_t = torch.from_numpy(g).to(DEV)
print('testa congelata: lm_head %s, norm %s, device %s\n' % (W.shape, g.shape, DEV))

d = np.load(COPPIE)
X, y = d['X'].astype(np.float32), d['y']
X, y = X[:-1], y[1:]                       # orizzonte t+2
n = len(X)
ntr = int(n * 0.8)
Xtr = torch.from_numpy(X[:ntr]).to(DEV)
ytr = torch.from_numpy(y[:ntr]).to(DEV)
Xte = torch.from_numpy(X[ntr:]).to(DEV)
yte = torch.from_numpy(y[ntr:]).to(DEV)
print('prosa t+2: n=%d (tr %d / te %d)\n' % (n, ntr, n - ntr))


def rms(x, w, eps=1e-6):
    return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + eps) * w


def acc(P, ycmp):
    with torch.no_grad():
        return float((rms(P, g_t) @ W_t.T).argmax(1).eq(ycmp).float().mean())


# bersaglio: la riga di lm_head del token vero (spazio in cui vive la testa)
Ttr = W_t[ytr]
mu, sd = Xtr.mean(0, keepdim=True), Xtr.std(0, keepdim=True) + 1e-6


class Adapter(nn.Module):
    def __init__(self, d=4096, h=1024):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, h), nn.GELU(),
            nn.Linear(h, h), nn.GELU(),
            nn.Linear(h, d),
        )
        self.scala = nn.Parameter(torch.ones(1))

    def forward(self, x):
        return self.net((x - mu) / sd) * self.scala


# distillazione: distribuzione del modello sui top-k, calcolata UNA volta.
# E si estraggono anche le RIGHE di lm_head dei top-k: dentro il ciclo servono
# solo quelle 32, non tutte le 129.280. Ricalcolare la proiezione piena a ogni
# epoca per leggerne 32 numeri costa 1,7 TFLOP a giro -- 45 minuti invece di
# un minuto. Stessa lezione dell'orchestrazione che mangia i FLOP, in PyTorch.
with torch.no_grad():
    lm_tr = rms(Xtr, g_t) @ W_t.T
    v, idx = lm_tr.topk(TOPK, dim=1)
    q_tr = F.softmax(v, dim=1)
    W_topk = W_t[idx]                      # [n_tr, TOPK, 4096], estratte una volta
    del lm_tr
    torch.cuda.empty_cache()

print('%-13s %8s %8s   %s' % ('modello', 'p_train', 'p_test', 'lettura'))
for nome, H, EP, LR in (('MLP h=512', 512, 4000, 1e-3), ('MLP h=1024', 1024, 4000, 1e-3)):
    torch.manual_seed(0)
    m = Adapter(h=H).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), lr=LR, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, EP)
    best_te, best_tr = 0.0, 0.0
    for ep in range(EP):
        m.train(); opt.zero_grad()
        P = m(Xtr)
        # solo le 32 righe che servono: bmm [n,1,4096] x [n,4096,TOPK]
        lp = torch.bmm(rms(P, g_t).unsqueeze(1), W_topk.transpose(1, 2)).squeeze(1)
        perdita = F.mse_loss(P, Ttr) + 0.1 * F.kl_div(F.log_softmax(lp, 1), q_tr, reduction='batchmean')
        perdita.backward(); opt.step(); sched.step()
        if ep % 100 == 99:
            m.eval()
            a_te, a_tr = acc(m(Xte), yte), acc(m(Xtr), ytr)
            if a_te > best_te:
                best_te = a_te
            best_tr = max(best_tr, a_tr)
    if best_tr < 0.55:
        lettura = 'SOTTO-ADDESTRATO (non impara nemmeno il train): risultato NULLO'
    elif best_te < 0.614:
        lettura = 'sovra-adatta: il collo sono i DATI'
    else:
        lettura = 'BATTE la ridge: serve nonlinearita'
    print('%-13s %8.3f %8.3f   %s' % (nome, best_tr, best_te, lettura))

print('\nriferimenti stesso split: BIGRAMMA 0.469 | ridge lineare 0.614 (test)')
