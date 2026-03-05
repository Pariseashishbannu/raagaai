"""Llama-3-style causal Transformer for Carnatic svara generation.

Architecture: 4 layers, 4 query heads / 2 KV heads (GQA), 128 embed dim, ~1.5M params.
Modern components: RoPE, RMSNorm, SwiGLU FFN, Grouped Query Attention.
Fits comfortably in 4GB VRAM for training with batch_size=32.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


# ── RMSNorm ──────────────────────────────────────────────────────────────────

class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization (Zhang & Sennrich, 2019).

    ~15% faster than LayerNorm — skips mean computation and centering.
    Used by Llama 3, Mistral, Gemma 2, Phi-3, Qwen 2.5.
    """

    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return x / rms * self.weight


# ── Rotary Position Embeddings (RoPE) ────────────────────────────────────────

class RotaryPositionalEmbedding(nn.Module):
    """Rotary Position Embeddings (Su et al., 2021).

    Encodes position via rotation matrices — enables:
      - Relative position awareness (better musical pattern recognition)
      - Length generalization beyond training sequences
      - Decaying inter-token dependency by distance (natural for music)
    """

    def __init__(self, dim: int, max_seq_len: int = 2048, theta: float = 10000.0):
        super().__init__()
        # Precompute inverse frequencies
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)
        # Precompute cos/sin cache
        self._build_cache(max_seq_len)

    def _build_cache(self, max_seq_len: int) -> None:
        t = torch.arange(max_seq_len, dtype=self.inv_freq.dtype)
        freqs = torch.outer(t, self.inv_freq)  # (seq_len, dim/2)
        # Duplicate for pairs: [cos, cos, ...], [sin, sin, ...]
        cos_cached = freqs.cos()
        sin_cached = freqs.sin()
        self.register_buffer("cos_cached", cos_cached, persistent=False)
        self.register_buffer("sin_cached", sin_cached, persistent=False)

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
    """Apply RoPE to query and key tensors.

    Args:
        q: (batch, num_heads, seq_len, head_dim)
        k: (batch, num_kv_heads, seq_len, head_dim)
        cos: (seq_len, head_dim/2)
        sin: (seq_len, head_dim/2)
    """
    def _rotate(x: torch.Tensor, cos_: torch.Tensor, sin_: torch.Tensor) -> torch.Tensor:
        d = x.shape[-1]
        x1 = x[..., : d // 2]
        x2 = x[..., d // 2:]
        # Reshape cos/sin for broadcasting: (1, 1, seq_len, head_dim/2)
        cos_ = cos_.unsqueeze(0).unsqueeze(0)
        sin_ = sin_.unsqueeze(0).unsqueeze(0)
        return torch.cat([
            x1 * cos_ - x2 * sin_,
            x2 * cos_ + x1 * sin_,
        ], dim=-1)

    q_rotated = _rotate(q, cos, sin)
    k_rotated = _rotate(k, cos, sin)
    return q_rotated, k_rotated


# ── Grouped Query Attention (GQA) ───────────────────────────────────────────

class GroupedQueryAttention(nn.Module):
    """Grouped Query Attention (Ainslie et al., 2023).

    Uses fewer KV heads than query heads — 2× faster inference with KV-cache,
    with no quality loss at this scale. Used by Llama 3, Mistral, Gemma 2.

    Config: 4 query heads, 2 KV heads → each KV head serves 2 query heads.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int = 4,
        num_kv_heads: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        assert num_heads % num_kv_heads == 0, "num_heads must be divisible by num_kv_heads"

        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = embed_dim // num_heads
        self.num_groups = num_heads // num_kv_heads

        # Separate projections for Q (full heads) and K, V (fewer heads)
        self.q_proj = nn.Linear(embed_dim, num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(embed_dim, num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(embed_dim, num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(num_heads * self.head_dim, embed_dim, bias=False)

        self.attn_dropout = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, seq_len, _ = x.shape

        # Project to Q, K, V
        q = self.q_proj(x).view(batch, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # Apply RoPE
        q, k = apply_rotary_emb(q, k, cos, sin)

        # Expand KV heads for grouped query attention
        # (batch, num_kv_heads, seq, head_dim) → (batch, num_heads, seq, head_dim)
        if self.num_groups > 1:
            k = k.unsqueeze(2).expand(-1, -1, self.num_groups, -1, -1)
            k = k.reshape(batch, self.num_heads, seq_len, self.head_dim)
            v = v.unsqueeze(2).expand(-1, -1, self.num_groups, -1, -1)
            v = v.reshape(batch, self.num_heads, seq_len, self.head_dim)

        # Scaled dot-product attention
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask.unsqueeze(0).unsqueeze(0), float("-inf"))

        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)

        out = torch.matmul(attn_weights, v)  # (batch, heads, seq, head_dim)
        out = out.transpose(1, 2).contiguous().view(batch, seq_len, -1)

        return self.o_proj(out)


# ── SwiGLU Feed-Forward Network ─────────────────────────────────────────────

class SwiGLUFFN(nn.Module):
    """SwiGLU gated FFN (Shazeer, 2020).

    gate = SiLU(x · W_gate)
    up   = x · W_up
    out  = (gate ⊙ up) · W_down

    Consistently outperforms GELU/ReLU FFN at all model scales.
    Used by Llama 3, Mistral, Gemma 2, PaLM, Phi-3.
    """

    def __init__(self, embed_dim: int, hidden_dim: int | None = None, dropout: float = 0.1):
        super().__init__()
        # SwiGLU uses 2/3 of the standard 4× hidden dim (compensates for the extra gate projection)
        if hidden_dim is None:
            hidden_dim = int(embed_dim * 8 / 3)
            # Round to nearest multiple of 8 for hardware efficiency
            hidden_dim = ((hidden_dim + 7) // 8) * 8

        self.gate_proj = nn.Linear(embed_dim, hidden_dim, bias=False)
        self.up_proj = nn.Linear(embed_dim, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, embed_dim, bias=False)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x)))


# ── Transformer Block ───────────────────────────────────────────────────────

class TransformerBlock(nn.Module):
    """Pre-norm Transformer block: RMSNorm → GQA → residual → RMSNorm → SwiGLU → residual."""

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
        # Pre-norm attention with residual
        x = x + self.attn(self.attn_norm(x), cos, sin, mask)
        # Pre-norm FFN with residual
        x = x + self.ffn(self.ffn_norm(x))
        return x


# ── SvaraTransformer ─────────────────────────────────────────────────────────

class SvaraTransformer(nn.Module):
    """Llama-3-style causal decoder Transformer for svara sequence generation.

    Modern architecture with RoPE, RMSNorm, GQA, and SwiGLU FFN.
    Drop-in replacement for the previous GPT-2-style model — same external API.
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

        # Default: half the query heads for KV (GQA)
        if num_kv_heads is None:
            num_kv_heads = max(1, num_heads // 2)

        head_dim = embed_dim // num_heads

        # Token embedding (no positional embedding — RoPE handles position)
        self.token_emb = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.drop = nn.Dropout(dropout)

        # RoPE
        self.rope = RotaryPositionalEmbedding(head_dim, max_seq_len, rope_theta)

        # Transformer blocks
        self.layers = nn.ModuleList([
            TransformerBlock(embed_dim, num_heads, num_kv_heads, dropout=dropout)
            for _ in range(num_layers)
        ])

        # Final norm + output head
        self.norm_f = RMSNorm(embed_dim)
        self.head = nn.Linear(embed_dim, vocab_size, bias=False)

        # Weight tying: share token embedding weights with output projection
        self.head.weight = self.token_emb.weight

        self._init_weights()

    def _init_weights(self):
        for p in self.parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Forward pass with optional loss computation.

        Args:
            input_ids: (batch, seq_len) token IDs.
            labels: (batch, seq_len) target IDs, -100 for ignored positions.

        Returns:
            Dict with 'logits' and optionally 'loss'.
        """
        batch_size, seq_len = input_ids.shape

        x = self.token_emb(input_ids)
        x = self.drop(x)

        # Causal mask: prevent attending to future tokens
        causal_mask = torch.triu(
            torch.ones(seq_len, seq_len, device=x.device, dtype=torch.bool), diagonal=1
        )

        # RoPE cos/sin
        cos, sin = self.rope(seq_len)
        cos = cos.to(x.device)
        sin = sin.to(x.device)

        # Pass through Transformer blocks
        for layer in self.layers:
            x = layer(x, cos, sin, causal_mask)

        x = self.norm_f(x)
        logits = self.head(x)

        result = {"logits": logits}

        if labels is not None:
            loss = F.cross_entropy(
                logits.view(-1, self.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )
            result["loss"] = loss

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
        """Autoregressive generation with temperature sampling.

        Args:
            input_ids: (1, prefix_len) conditioning tokens.
            max_new_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (lower = more deterministic).
            top_k: Top-k filtering (0 = disabled).
            logit_mask: (vocab_size,) mask with 0.0 for valid, -inf for invalid.
                        Applied at each step for constrained decoding.
            eos_token_id: Stop generation when this token is produced.

        Returns:
            (1, prefix_len + generated_len) tensor of token IDs.
        """
        self.eval()
        generated = input_ids.clone()

        for _ in range(max_new_tokens):
            # Truncate to max_seq_len if needed
            context = generated[:, -self.max_seq_len:]

            out = self.forward(context)
            next_logits = out["logits"][:, -1, :]  # (1, vocab)

            # Apply raga constraint mask
            if logit_mask is not None:
                next_logits = next_logits + logit_mask.unsqueeze(0)

            # Temperature
            next_logits = next_logits / max(temperature, 1e-8)

            # Top-k filtering
            if top_k > 0:
                top_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
                threshold = top_vals[:, -1].unsqueeze(-1)
                next_logits[next_logits < threshold] = float("-inf")

            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            generated = torch.cat([generated, next_token], dim=1)

            if next_token.item() == eos_token_id:
                break

        return generated

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def load_model(
    checkpoint_path: str,
    device: str = "cpu",
) -> tuple[SvaraTransformer, dict]:
    """Load a trained model from checkpoint.

    Returns:
        (model, config_dict) tuple.
    """
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    config = checkpoint["config"]

    model = SvaraTransformer(
        vocab_size=config["vocab_size"],
        embed_dim=config.get("embed_dim", 128),
        num_heads=config.get("num_heads", 4),
        num_layers=config.get("num_layers", 4),
        max_seq_len=config.get("max_seq_len", 256),
        dropout=config.get("dropout", 0.0),  # No dropout at inference
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    return model, config
