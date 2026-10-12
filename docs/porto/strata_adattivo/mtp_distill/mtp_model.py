"""mtp_model.py - il layer MTP di Qwen3.8-Flash-Next in PyTorch, trascritto da src/core/mtp.cpp del motore Strata.

Cella i: ingresso = residuo finale a 4 flussi del modello principale alla posizione i (R_i, hc*n_embd = 10240) e il token
alla posizione i+1; posizione rope i; uscita = logits del token i+2 e il proprio residuo (ingresso del passo successivo).

    e   = fc_embedding( rms(embed(tok)) * (1+w_e) )
    h   = fc_hidden per flusso( rms_10240(R) * (1+w_h) )          (una RMS su tutti i 10240 valori: default del motore)
    R   = h + e (broadcast su ogni flusso)
    attn HC read  -> mixed, inj     (gr_read: norma per flusso, down/silu(/hc)/up, media pesata da sigmoid, inject)
    K,V = k_proj/v_proj(mixed), k_norm (1+w), rope neox parziale 64/256, theta 1e7
    q   = q_proj(mixed) [24 teste x (q 256 | gate 256)], q_norm, rope; attenzione causale densa GQA 24/2, 1/sqrt(256)
    out = attn * sigmoid(gate); bo = o_proj(out)
    R  += bo * 2 sigmoid(inj/hc)                                    (gr_write, piegata nella lettura successiva)
    mlp HC read   -> mixed2, inj2
    router softmax(512) top-10 rinormalizzato (clamp 2^-14); esperti SwiGLU 640; esperto condiviso * sigmoid(gate_s . x)
    R  += y * 2 sigmoid(inj2/hc)
    sample = gr_read(R, mixer, senza inject);  logits = head[sottoinsieme draft_vocab] @ sample

Pesi: il blocco BF16 originale (mtp-manifest.json + tensors/*.bin), gli esperti instradati dal pacco del motore
(experts.bin, Q2_0 dequantizzato: sono CONGELATI e il motore usa quelli), embedding e testa dal GGUF del target
(token_embd IQ3_S, output Q5_K, dequantizzati con gguf-py; in cache come .npy bf16).

Allenabili (~90M): attenzione (q/k/v/o), router, esperto condiviso (+ gate), le tre hyper-connection, fc_embedding,
fc_hidden, tutte le norme.  Congelati: esperti instradati, testa, embedding, indexer (inutilizzato: attenzione densa).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

H, HCN, HC, HC_LR = 2560, 10240, 4, 320
NH, NKV, HD, N_ROT = 24, 2, 256, 64
NE, FF, K = 512, 640, 10
THETA = 1e7
EPS = 1e-6
INTER_CODES = 2 * FF * (H // 64) * 16
DOWN_CODES = H * (FF // 64) * 16
INTER_SCALES = 2 * FF * (H // 64) * 2
DOWN_SCALES = H * (FF // 64) * 2
BLOB = INTER_CODES + DOWN_CODES + INTER_SCALES + DOWN_SCALES
assert BLOB == 1382400

TRAINABLE_PREFIXES = ("self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj", "self_attn.q_norm",
                      "self_attn.k_norm", "mlp.gate.weight", "mlp.shared_expert.", "mlp.shared_expert_gate",
                      "attn_hyper_connection.", "mlp_hyper_connection.", "hyper_connection_mixer.", "fc_embedding",
                      "fc_hidden", "pre_fc_norm_embedding", "pre_fc_norm_hidden")
FROZEN_PASSTHROUGH = ("self_attn.indexer.",)   # nel pacco, mai usati dal drafter


def short_name(name: str) -> str:
    s = name[len("mtp."):] if name.startswith("mtp.") else name
    return s[len("layers.0."):] if s.startswith("layers.0.") else s


def bf16_bits_to_f32(u16: np.ndarray) -> np.ndarray:
    return (u16.astype(np.uint32) << 16).view(np.float32)


def load_bf16_block(src: Path) -> dict[str, torch.Tensor]:
    """I 29 tensori densi del blocco BF16 (gli esperti instradati restano fuori: vedi ExpertBank)."""
    manifest = json.loads((src / "mtp-manifest.json").read_text())
    out = {}
    for t in manifest:
        if "mlp.experts." in t["name"]:
            continue
        raw = np.fromfile(src / t["file"].replace("\\", "/"), dtype="<u2").reshape(t["shape"])
        out[short_name(t["name"])] = torch.from_numpy(bf16_bits_to_f32(raw).copy())
    return out


def rms_norm(x: torch.Tensor, w1: torch.Tensor, eps: float = EPS) -> torch.Tensor:
    """x * rsqrt(mean(x^2)+eps) * w1 sull'ultimo asse (w1 = 1 + w, come il motore memorizza le norme)."""
    xf = x.float()
    return (xf * torch.rsqrt(xf.pow(2).mean(-1, keepdim=True) + eps) * w1.float()).to(x.dtype)


def rope_neox_partial(x: torch.Tensor, pos: torch.Tensor) -> torch.Tensor:
    """x [..., L, heads, HD], pos [..., L] int: ruota le prime N_ROT dimensioni a coppie (i, i + N_ROT/2), theta 1e7."""
    half = N_ROT // 2
    inv = THETA ** (-torch.arange(0, half, device=x.device, dtype=torch.float32) / half)   # [half]
    ang = pos.float().unsqueeze(-1) * inv                                                 # [..., L, half]
    cos, sin = ang.cos().unsqueeze(-2), ang.sin().unsqueeze(-2)                           # [..., L, 1, half]
    x1, x2, rest = x[..., :half].float(), x[..., half:N_ROT].float(), x[..., N_ROT:]
    o1 = x1 * cos - x2 * sin
    o2 = x1 * sin + x2 * cos
    return torch.cat([o1.to(x.dtype), o2.to(x.dtype), rest], dim=-1)


class ExpertBank:
    """I 512 esperti instradati, congelati.  `q2`: dal pacco del motore (experts.bin, Q2_0, cio' che il motore usa);
    `bf16`: dal checkpoint BF16 (per confronto).  Dequantizzati tutti in bf16 sul device (5 GB) o per-esperto a richiesta."""

    def __init__(self, mode: str, path: Path, device: torch.device, resident: bool):
        self.mode, self.device, self.resident = mode, device, resident
        if mode == "q2":
            self.blob = np.memmap(path / "experts.bin", dtype=np.uint8, mode="r", shape=(NE, BLOB))
        else:
            self.gu = np.memmap(path / "tensors" / "mtp.layers.0.mlp.experts.gate_up_proj.bin", dtype="<u2", mode="r", shape=(NE, 2 * FF, H))
            self.dn = np.memmap(path / "tensors" / "mtp.layers.0.mlp.experts.down_proj.bin", dtype="<u2", mode="r", shape=(NE, H, FF))
        self.cache: dict[int, tuple[torch.Tensor, torch.Tensor]] = {}
        if resident:
            for e in range(NE):
                self.cache[e] = self._load(e)

    @staticmethod
    def _dequant_q2(codes: np.ndarray, scales: np.ndarray, rows: int, cols: int) -> torch.Tensor:
        """codes [rows, cols/64, 16] uint8, scales [rows, cols/64] fp16 -> [rows, cols] f32 ((c - 1) * d)."""
        c = torch.from_numpy(np.ascontiguousarray(codes)).reshape(rows, cols // 64, 16)
        q = torch.stack([(c >> s) & 3 for s in (0, 2, 4, 6)], dim=-1).reshape(rows, cols // 64, 64).float() - 1.0
        d = torch.from_numpy(np.ascontiguousarray(scales).view(np.float16).astype(np.float32)).reshape(rows, cols // 64, 1)
        return (q * d).reshape(rows, cols)

    def _load(self, e: int) -> tuple[torch.Tensor, torch.Tensor]:
        if self.mode == "q2":
            b = np.asarray(self.blob[e])
            o = 0
            inter_c = b[o:o + INTER_CODES].reshape(2 * FF, H // 64, 16); o += INTER_CODES
            down_c = b[o:o + DOWN_CODES].reshape(H, FF // 64, 16); o += DOWN_CODES
            inter_s = b[o:o + INTER_SCALES].reshape(2 * FF, H // 64, 2); o += INTER_SCALES
            down_s = b[o:o + DOWN_SCALES].reshape(H, FF // 64, 2)
            inter = self._dequant_q2(inter_c, inter_s, 2 * FF, H)      # righe interleaved: 2r gate r, 2r+1 up r
            gu = torch.cat([inter[0::2], inter[1::2]], dim=0)          # [gate 640 | up 640] x 2560
            dn = self._dequant_q2(down_c, down_s, H, FF)               # [2560, 640]
        else:
            gu = torch.from_numpy(bf16_bits_to_f32(np.asarray(self.gu[e])).copy())
            dn = torch.from_numpy(bf16_bits_to_f32(np.asarray(self.dn[e])).copy())
        # su CPU i GEMM bf16 di PyTorch sono 50-100x piu' lenti di quelli f32: pesi in f32 fuori da CUDA
        wdt = torch.bfloat16 if self.device.type == 'cuda' else torch.float32
        return gu.to(self.device, wdt), dn.to(self.device, wdt)

    def get(self, e: int) -> tuple[torch.Tensor, torch.Tensor]:
        w = self.cache.get(e)
        if w is None:
            w = self._load(e)
            if len(self.cache) < 64:   # piccola cache per la prova su CPU
                self.cache[e] = w
        return w


def gguf_rows(gguf_path: Path, name: str, cache_dir: Path, tools_dir: Path) -> torch.Tensor:
    """Un tensore 2-D del GGUF dequantizzato (gguf-py) come bf16 [rows, cols]; in cache come .npy di bit bf16."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{name}.bf16.npy"
    if cache.exists():
        return torch.from_numpy(np.load(cache).view(np.int16)).view(torch.bfloat16)
    sys.path.insert(0, str(tools_dir))
    from gguf_reader import GGUFFile          # il lettore di Strata (conosce il tipo 42)
    from gguf import quants, GGMLQuantizationType as Q   # gguf-py di pip per i tipi standard
    g = GGUFFile(gguf_path)
    t = next(x for x in g.tensors if x.name == name)
    rows, cols = t.shape[1], t.shape[0]              # GGUF: dim 0 e' la piu' veloce
    nbytes = t.expected_bytes
    nbytes = nbytes() if callable(nbytes) else nbytes
    raw = np.memmap(gguf_path, dtype=np.uint8, mode="r", offset=g.data_start + t.offset, shape=(nbytes,))
    out = np.empty((rows, cols), dtype=np.uint16)
    step = 8192
    per_row = nbytes // rows
    qt = Q[t.type_name]
    for r0 in range(0, rows, step):
        r1 = min(rows, r0 + step)
        chunk = np.asarray(raw[r0 * per_row:r1 * per_row]).reshape(r1 - r0, per_row)
        f32 = quants.dequantize(chunk, qt).astype(np.float32)
        out[r0:r1] = (f32.view(np.uint32) + 0x7FFF + ((f32.view(np.uint32) >> 16) & 1)) >> 16
    np.save(cache, out)
    return torch.from_numpy(out.view(np.int16)).view(torch.bfloat16)


class MtpLayer(nn.Module):
    def __init__(self, dense: dict[str, torch.Tensor], experts: ExpertBank, embed: torch.Tensor, head_rows: torch.Tensor,
                 hnorm_per_stream: bool = False, train_fc: bool = True):
        super().__init__()
        self.experts = experts
        self.hnorm_per_stream = hnorm_per_stream
        self.register_buffer("embed", embed, persistent=False)            # [V, H] bf16, congelato
        self.register_buffer("head_rows", head_rows, persistent=False)    # [Vd, H] bf16, congelato (righe del sottoinsieme)
        self.params = nn.ParameterDict()
        self.frozen: dict[str, torch.Tensor] = {}
        for name, w in dense.items():
            trainable = name.startswith(TRAINABLE_PREFIXES) and not name.startswith(FROZEN_PASSTHROUGH)
            if not train_fc and name.startswith(("fc_embedding", "fc_hidden", "pre_fc_norm")):
                trainable = False
            if trainable:
                self.params[name.replace(".", "__")] = nn.Parameter(w.clone().float())
            else:
                self.frozen[name] = w.clone()

    def p(self, name: str) -> torch.Tensor:
        key = name.replace(".", "__")
        if key in self.params:
            return self.params[key]
        return self.frozen[name].to(self.embed.device)

    def norm1(self, name: str) -> torch.Tensor:   # norme memorizzate grezze nel checkpoint: il motore usa 1 + w
        return 1.0 + self.p(name)

    def trainable_tensors(self) -> dict[str, torch.Tensor]:
        return {k.replace("__", "."): v.detach() for k, v in self.params.items()}

    # ---- hyper-connection
    def gr_read(self, R: torch.Tensor, prefix: str, inject: bool):
        """R [..., HC, H] -> mixed [..., H], inj [..., HC] (gr.hpp: lo = silu((w_down . xn)/hc), mixed = mean_c xn*sigmoid(w_up . lo))."""
        w_norm = self.norm1(prefix + ".hc_norm.weight").view(HC, H)
        xn = rms_norm(R, w_norm)                                                        # per flusso
        xf = xn.reshape(*R.shape[:-2], HCN)
        lo = F.silu(F.linear(xf, self.p(prefix + ".input_mix_weight_down.weight").to(xf.dtype)) / HC)   # [..., 320]
        gate = F.linear(lo, self.p(prefix + ".input_mix_weight_up.weight").to(lo.dtype))              # [..., 10240]
        mixed = (xn * torch.sigmoid(gate.view(*R.shape[:-2], HC, H))).mean(-2)
        inj = F.linear(xf, self.p(prefix + ".block_inject_weight.weight").to(xf.dtype)) if inject else None
        return mixed, inj

    @staticmethod
    def gr_write(R: torch.Tensor, block_out: torch.Tensor, inj: torch.Tensor) -> torch.Tensor:
        w = 2.0 * torch.sigmoid(inj.float() / HC)                        # [..., HC]
        return R + block_out.unsqueeze(-2).to(R.dtype) * w.unsqueeze(-1).to(R.dtype)

    # ---- il davanti del layer: embedding, fc, hyper-connection dell'attenzione, K/V
    def front(self, R_in: torch.Tensor, tok: torch.Tensor, pos: torch.Tensor):
        B, L = tok.shape
        dt = torch.bfloat16 if R_in.is_cuda else torch.float32
        emb = F.embedding(tok, self.embed).to(dt)                                               # [B, L, H]
        e2 = F.linear(rms_norm(emb, self.norm1("pre_fc_norm_embedding.weight")), self.p("fc_embedding.weight").to(dt))
        Rf = R_in.to(dt)
        if self.hnorm_per_stream:
            hn = rms_norm(Rf.view(B, L, HC, H), self.norm1("pre_fc_norm_hidden.weight").view(HC, H))
        else:
            hn = rms_norm(Rf.view(B, L, HCN), self.norm1("pre_fc_norm_hidden.weight")).view(B, L, HC, H)
        h2 = F.linear(hn, self.p("fc_hidden.weight").to(dt))                                    # [B, L, HC, H]
        R = h2 + e2.unsqueeze(-2)
        mixed, inj = self.gr_read(R, "attn_hyper_connection", inject=True)
        k = F.linear(mixed, self.p("self_attn.k_proj.weight").to(dt)).view(B, L, NKV, HD)
        v = F.linear(mixed, self.p("self_attn.v_proj.weight").to(dt)).view(B, L, NKV, HD)
        k = rope_neox_partial(rms_norm(k, self.norm1("self_attn.k_norm.weight")), pos)
        qfull = F.linear(mixed, self.p("self_attn.q_proj.weight").to(dt)).view(B, L, NH, 2 * HD)
        q = rope_neox_partial(rms_norm(qfull[..., :HD], self.norm1("self_attn.q_norm.weight")), pos)
        gate = qfull[..., HD:]
        return R, inj, q, gate, k, v

    def attend(self, q, k0, v0, extra_k, extra_v):
        """q [B,L,NH,HD] alla cella c+j; k0/v0 [B,L,NKV,HD] del passo 0 (chiavi alle celle <= c: maschera causale sulla
        cella di partenza); extra_k/v [B,L,J,NKV,HD]: le chiavi della catena stessa alle celle c+1..c+j (J = j)."""
        B, L = q.shape[:2]
        rep = NH // NKV
        qh = q.permute(0, 2, 1, 3).float()                                     # [B, NH, L, HD]
        kh = k0.permute(0, 2, 1, 3).float().repeat_interleave(rep, dim=1)      # [B, NH, L, HD]  (teste q h -> kv h // 12)
        vh = v0.permute(0, 2, 1, 3).float().repeat_interleave(rep, dim=1)
        scale = 1.0 / math.sqrt(HD)
        s = torch.matmul(qh, kh.transpose(-1, -2)) * scale                     # [B, NH, L(q), L(k)]
        causal = torch.ones(L, L, dtype=torch.bool, device=q.device).tril()
        s = s.masked_fill(~causal, float("-inf"))
        if extra_k is not None and extra_k.shape[2] > 0:
            J = extra_k.shape[2]
            ek = extra_k.permute(0, 3, 1, 2, 4).float().repeat_interleave(rep, dim=1)   # [B, NH, L, J, HD]
            ev = extra_v.permute(0, 3, 1, 2, 4).float().repeat_interleave(rep, dim=1)
            se = (qh.unsqueeze(-2) * ek).sum(-1) * scale                        # [B, NH, L, J]
            s = torch.cat([s, se], dim=-1)
            w = torch.softmax(s, dim=-1)
            out = torch.matmul(w[..., :L], vh) + (w[..., L:].unsqueeze(-1) * ev).sum(-2)
        else:
            w = torch.softmax(s, dim=-1)
            out = torch.matmul(w, vh)
        return out.permute(0, 2, 1, 3).to(q.dtype)                              # [B, L, NH, HD]

    def rest(self, R, inj, attn, gate, pos_dtype):
        B, L = attn.shape[:2]
        dt = attn.dtype
        out = (attn.float() * torch.sigmoid(gate.float())).to(dt).reshape(B, L, NH * HD)
        bo = F.linear(out, self.p("self_attn.o_proj.weight").to(dt))
        R = self.gr_write(R, bo, inj)
        mixed, inj2 = self.gr_read(R, "mlp_hyper_connection", inject=True)
        x = mixed.reshape(B * L, H)
        # router: softmax su 512, top-10, rinormalizzato (router_top10.hpp)
        logits = F.linear(x.float(), self.p("mlp.gate.weight").float())
        probs = torch.softmax(logits, dim=-1)
        w, ids = torch.topk(probs, K, dim=-1)
        w = w / w.sum(-1, keepdim=True).clamp_min(2.0 ** -14)
        y = torch.zeros(B * L, H, dtype=torch.float32, device=x.device)
        flat_ids = ids.reshape(-1)
        flat_w = w.reshape(-1)
        rows = torch.arange(B * L, device=x.device).repeat_interleave(K)
        for e in torch.unique(flat_ids).tolist():
            sel = (flat_ids == e).nonzero(as_tuple=True)[0]
            gu, dn = self.experts.get(e)
            xe = x[rows[sel]].to(gu.dtype)
            hgu = F.linear(xe, gu)
            act = F.silu(hgu[:, :FF].float()) * hgu[:, FF:].float()
            ye = F.linear(act.to(dn.dtype), dn).float() * flat_w[sel].unsqueeze(-1)
            y.index_add_(0, rows[sel], ye)
        # esperto condiviso: down(silu(gate x) * up x) * sigmoid(gate_s . x)
        sg = F.silu(F.linear(x, self.p("mlp.shared_expert.gate_proj.weight").to(dt)).float())
        su = F.linear(x, self.p("mlp.shared_expert.up_proj.weight").to(dt)).float()
        sh = F.linear((sg * su).to(dt), self.p("mlp.shared_expert.down_proj.weight").to(dt)).float()
        g = torch.sigmoid(F.linear(x.float(), self.p("mlp.shared_expert_gate.weight").float()))   # [BL, 1]
        y = (y + sh * g).view(B, L, H).to(dt)
        R = self.gr_write(R, y, inj2)
        sample, _ = self.gr_read(R, "hyper_connection_mixer", inject=False)
        return R, sample

    def head(self, sample: torch.Tensor) -> torch.Tensor:
        """Logits sul sottoinsieme del draft head (le righe della testa principale per draft_vocab.bin), f32."""
        return F.linear(sample.to(self.head_rows.dtype), self.head_rows).float()   # testa bf16 su CUDA, f32 su CPU

    def chain(self, R_in: torch.Tensor, ids: torch.Tensor, steps: int):
        """Catena srotolata.  R_in [B, L, HCN] = residui del target alle posizioni 0..L-1; ids [B, L+steps] token alle
        posizioni 0..L+steps-1.  Passo j (0-based), cella c: ingresso (R^(j)_c, ids[c+j+1]) alla posizione c+j; predice
        ids[c+j+2].  Restituisce la lista dei `sample` [B, L, H] per passo (la testa va applicata a parte, a pezzi)."""
        B, L = R_in.shape[:2]
        dev = R_in.device
        cells = torch.arange(L, device=dev).unsqueeze(0).expand(B, L)
        samples = []
        R_cur = R_in.view(B, L, HC, H)
        k0 = v0 = None
        ek, ev = [], []
        for j in range(steps):
            tok = ids[:, j + 1:j + 1 + L]
            pos = cells + j
            R, inj, q, gate, k, v = self.front(R_cur.reshape(B, L, HCN), tok, pos)
            if j == 0:
                k0, v0 = k, v
                attn = self.attend(q, k0, v0, None, None)
            else:
                ek.append(k)
                ev.append(v)
                attn = self.attend(q, k0, v0, torch.stack(ek, dim=2), torch.stack(ev, dim=2))
            R_out, sample = self.rest(R, inj, attn, gate, None)
            samples.append(sample)
            R_cur = R_out
        return samples


def build_model(bf16_dir: Path, rt_dir: Path, gguf_path: Path, tools_dir: Path, cache_dir: Path, device: torch.device,
                experts_mode: str = "q2", experts_resident: bool | None = None, hnorm_per_stream: bool = False,
                train_fc: bool = True, full_head: bool = False) -> tuple[MtpLayer, torch.Tensor]:
    dense = load_bf16_block(bf16_dir)
    if experts_resident is None:
        experts_resident = device.type == "cuda"
    bank = ExpertBank(experts_mode, rt_dir if experts_mode == "q2" else bf16_dir, device, experts_resident)
    embed = gguf_rows(gguf_path, "token_embd.weight", cache_dir, tools_dir).to(device)
    head = gguf_rows(gguf_path, "output.weight", cache_dir, tools_dir)
    dvocab = torch.from_numpy(np.fromfile(rt_dir / "draft_vocab.bin", dtype="<i4").astype(np.int64))
    if full_head:
        dvocab = torch.arange(head.shape[0])
    head_rows = head[dvocab].to(device, torch.bfloat16 if device.type == 'cuda' else torch.float32)
    model = MtpLayer(dense, bank, embed, head_rows, hnorm_per_stream=hnorm_per_stream, train_fc=train_fc).to(device)
    return model, dvocab.to(device)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="conta i parametri allenabili del layer MTP")
    ap.add_argument("--bf16", default=r"D:\ds4_work\strata\Strata-data\mtp")
    a = ap.parse_args()
    dense = load_bf16_block(Path(a.bf16))
    n_tr = sum(w.numel() for n, w in dense.items() if n.startswith(TRAINABLE_PREFIXES) and not n.startswith(FROZEN_PASSTHROUGH))
    n_all = sum(w.numel() for w in dense.values())
    print(f"densi {len(dense)} tensori, {n_all / 1e6:.1f}M parametri; allenabili {n_tr / 1e6:.1f}M")
    for n, w in dense.items():
        tr = n.startswith(TRAINABLE_PREFIXES) and not n.startswith(FROZEN_PASSTHROUGH)
        print(f"  {'T' if tr else '-'} {n} {tuple(w.shape)}")
