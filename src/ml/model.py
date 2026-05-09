import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return x / rms * self.weight


class RotaryPositionalEmbedding(nn.Module):
    def __init__(self, dim: int, max_seq_len: int = 2048, theta: float = 10000.0):
        super().__init__()
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)
        self._build_cache(max_seq_len)

    def _build_cache(self, max_seq_len: int) -> None:
        # device= is required: when forward() rebuilds the cache after the model
        # has been .to('cuda'), inv_freq lives on GPU but torch.arange defaults
        # to CPU — torch.outer on mixed devices then crashes.
        t = torch.arange(max_seq_len, dtype=self.inv_freq.dtype, device=self.inv_freq.device)
        freqs = torch.outer(t, self.inv_freq)
        self.register_buffer("cos_cached", freqs.cos(), persistent=False)
        self.register_buffer("sin_cached", freqs.sin(), persistent=False)

    def forward(self, seq_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        if seq_len > self.cos_cached.shape[0]:
            self._build_cache(seq_len)
        return self.cos_cached[:seq_len], self.sin_cached[:seq_len]


def apply_rotary_emb(
    q: torch.Tensor,
    k: torch.Tensor,
    cos: torch.Tensor,
    sin: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    def _rotate(x: torch.Tensor, c: torch.Tensor, s: torch.Tensor) -> torch.Tensor:
        d = x.shape[-1]
        x1, x2 = x[..., : d // 2], x[..., d // 2 :]
        c, s = c.unsqueeze(0).unsqueeze(0), s.unsqueeze(0).unsqueeze(0)
        return torch.cat([x1 * c - x2 * s, x2 * c + x1 * s], dim=-1)

    return _rotate(q, cos, sin), _rotate(k, cos, sin)


class GroupedQueryAttention(nn.Module):
    """GQA with 4 query heads / 2 KV heads — same quality, cheaper KV cache."""

    def __init__(self, embed_dim: int, num_heads: int = 4, num_kv_heads: int = 2, dropout: float = 0.1):
        super().__init__()
        assert embed_dim % num_heads == 0
        assert num_heads % num_kv_heads == 0

        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = embed_dim // num_heads
        self.num_groups = num_heads // num_kv_heads
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(embed_dim, num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(embed_dim, num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(embed_dim, num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(num_heads * self.head_dim, embed_dim, bias=False)
        self.attn_dropout = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        B, T, _ = x.shape

        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        q, k = apply_rotary_emb(q, k, cos, sin)

        if self.num_groups > 1:
            k = k.unsqueeze(2).expand(-1, -1, self.num_groups, -1, -1).reshape(B, self.num_heads, T, self.head_dim)
            v = v.unsqueeze(2).expand(-1, -1, self.num_groups, -1, -1).reshape(B, self.num_heads, T, self.head_dim)

        attn = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        if mask is not None:
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn = self.attn_dropout(F.softmax(attn, dim=-1))
        out = torch.matmul(attn, v).transpose(1, 2).contiguous().view(B, T, -1)
        return self.o_proj(out)


class SwiGLUFFN(nn.Module):
    def __init__(self, embed_dim: int, hidden_dim: int | None = None, dropout: float = 0.1):
        super().__init__()
        if hidden_dim is None:
            # 8/3 of embed_dim compensates for the extra gate vs a standard 4x FFN
            hidden_dim = ((int(embed_dim * 8 / 3) + 7) // 8) * 8

        self.gate_proj = nn.Linear(embed_dim, hidden_dim, bias=False)
        self.up_proj = nn.Linear(embed_dim, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, embed_dim, bias=False)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x)))


class TransformerBlock(nn.Module):
    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        num_kv_heads: int,
        ffn_hidden_dim: int | None = None,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.attn_norm = RMSNorm(embed_dim)
        self.attn = GroupedQueryAttention(embed_dim, num_heads, num_kv_heads, dropout)
        self.ffn_norm = RMSNorm(embed_dim)
        self.ffn = SwiGLUFFN(embed_dim, ffn_hidden_dim, dropout)

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        x = x + self.attn(self.attn_norm(x), cos, sin, mask)
        x = x + self.ffn(self.ffn_norm(x))
        return x


class SvaraTransformer(nn.Module):
    """Causal decoder Transformer for Carnatic svara generation.

    ~1.5M params. RoPE + RMSNorm + GQA + SwiGLU. Trains comfortably in 4GB VRAM.
    """

    def __init__(
        self,
        vocab_size: int = 50,
        embed_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 4,
        max_seq_len: int = 256,
        dropout: float = 0.1,
        num_kv_heads: int | None = None,
        rope_theta: float = 10000.0,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.max_seq_len = max_seq_len
        self.vocab_size = vocab_size
        self.num_layers = num_layers

        if num_kv_heads is None:
            num_kv_heads = max(1, num_heads // 2)

        head_dim = embed_dim // num_heads

        self.token_emb = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.drop = nn.Dropout(dropout)
        self.rope = RotaryPositionalEmbedding(head_dim, max_seq_len, rope_theta)

        self.layers = nn.ModuleList([
            TransformerBlock(embed_dim, num_heads, num_kv_heads, dropout=dropout)
            for _ in range(num_layers)
        ])

        self.norm_f = RMSNorm(embed_dim)
        self.head = nn.Linear(embed_dim, vocab_size, bias=False)
        self.head.weight = self.token_emb.weight  # weight tying

        self._init_weights()

    def _init_weights(self) -> None:
        std = 0.02
        # Output projections of residual branches are scaled down to keep
        # activation variance stable as depth increases (same trick as GPT-2)
        residual_std = std / math.sqrt(2 * self.num_layers)

        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, mean=0.0, std=std)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=std)

        for block in self.layers:
            nn.init.normal_(block.attn.o_proj.weight, mean=0.0, std=residual_std)
            nn.init.normal_(block.ffn.down_proj.weight, mean=0.0, std=residual_std)

        # nn.init.normal_ overwrote the padding row that nn.Embedding had zeroed.
        # padding_idx only masks gradients, so without re-zeroing the pad embedding
        # stays frozen at random init and leaks into attention via real tokens.
        if self.token_emb.padding_idx is not None:
            with torch.no_grad():
                self.token_emb.weight[self.token_emb.padding_idx].zero_()

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        B, T = input_ids.shape

        x = self.drop(self.token_emb(input_ids))

        causal_mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1)
        cos, sin = self.rope(T)
        cos, sin = cos.to(x.device), sin.to(x.device)

        for layer in self.layers:
            x = layer(x, cos, sin, causal_mask)

        logits = self.head(self.norm_f(x))
        result: dict[str, torch.Tensor] = {"logits": logits}

        if labels is not None:
            result["loss"] = F.cross_entropy(
                logits.view(-1, self.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )

        return result

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 64,
        temperature: float = 0.8,
        top_k: int = 20,
        logit_mask: torch.Tensor | None = None,
        eos_token_id: int = 2,
    ) -> torch.Tensor:
        """Autoregressive generation with top-k sampling.

        logit_mask: (vocab_size,) tensor — 0.0 for allowed tokens, -inf for banned.
        Useful for raga-constrained decoding without touching sampling code.
        """
        self.eval()
        generated = input_ids.clone()

        for _ in range(max_new_tokens):
            context = generated[:, -self.max_seq_len :]
            logits = self.forward(context)["logits"][:, -1, :]

            if logit_mask is not None:
                logits = logits + logit_mask.unsqueeze(0)

            logits = logits / max(temperature, 1e-8)

            if top_k > 0:
                top_vals, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < top_vals[:, -1].unsqueeze(-1)] = float("-inf")

            next_token = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
            generated = torch.cat([generated, next_token], dim=1)

            if next_token.item() == eos_token_id:
                break

        return generated

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def load_model(checkpoint_path: str, device: str = "cpu") -> tuple["SvaraTransformer", dict]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    config = checkpoint["config"]

    model = SvaraTransformer(
        vocab_size=config["vocab_size"],
        embed_dim=config.get("embed_dim", 128),
        num_heads=config.get("num_heads", 4),
        num_layers=config.get("num_layers", 4),
        max_seq_len=config.get("max_seq_len", 256),
        dropout=0.0,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    return model, config
