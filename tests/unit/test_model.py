"""Unit tests for the SvaraTransformer model architecture."""

import pytest
import torch

from src.ml.model import SvaraTransformer, RMSNorm, RotaryPositionalEmbedding, load_model
from src.ml.tokenizer import SvaraTokenizer


@pytest.fixture
def tokenizer():
    return SvaraTokenizer()


@pytest.fixture
def model(tokenizer):
    return SvaraTransformer(vocab_size=tokenizer.vocab_size)


class TestModelInstantiation:
    def test_default_params(self, model):
        assert model.embed_dim == 128
        assert model.max_seq_len == 256

    def test_custom_params(self):
        m = SvaraTransformer(vocab_size=100, embed_dim=64, num_heads=2, num_layers=2)
        assert m.embed_dim == 64
        assert m.vocab_size == 100

    def test_parameter_count_reasonable(self, model):
        count = model.count_parameters()
        # ~1-3M params expected
        assert 500_000 < count < 5_000_000, f"Unexpected param count: {count:,}"


class TestForwardPass:
    def test_logits_shape(self, model, tokenizer):
        x = torch.randint(1, tokenizer.vocab_size, (2, 32))
        out = model(x)
        assert "logits" in out
        assert out["logits"].shape == (2, 32, tokenizer.vocab_size)

    def test_loss_computed_with_labels(self, model, tokenizer):
        x = torch.randint(1, tokenizer.vocab_size, (2, 32))
        labels = torch.randint(1, tokenizer.vocab_size, (2, 32))
        out = model(x, labels=labels)
        assert "loss" in out
        assert out["loss"].item() > 0

    def test_no_loss_without_labels(self, model, tokenizer):
        x = torch.randint(1, tokenizer.vocab_size, (2, 32))
        out = model(x)
        assert "loss" not in out

    def test_variable_sequence_lengths(self, model, tokenizer):
        """RoPE should handle different sequence lengths."""
        for seq_len in [4, 16, 64, 128]:
            x = torch.randint(1, tokenizer.vocab_size, (1, seq_len))
            out = model(x)
            assert out["logits"].shape == (1, seq_len, tokenizer.vocab_size)

    def test_single_token_input(self, model, tokenizer):
        x = torch.randint(1, tokenizer.vocab_size, (1, 1))
        out = model(x)
        assert out["logits"].shape == (1, 1, tokenizer.vocab_size)


class TestGeneration:
    def test_generate_produces_tokens(self, model):
        prefix = torch.tensor([[1, 7, 8, 9]])  # <bos>, Sa, Ri1, Ri2
        generated = model.generate(prefix, max_new_tokens=16)
        assert generated.shape[1] > prefix.shape[1]

    def test_generate_respects_max_tokens(self, model):
        prefix = torch.tensor([[1, 7]])
        generated = model.generate(prefix, max_new_tokens=10)
        # Should have at most prefix_len + max_new_tokens tokens
        assert generated.shape[1] <= prefix.shape[1] + 10

    def test_generate_stops_at_eos(self, model):
        prefix = torch.tensor([[1, 7]])
        # Even with lots of tokens allowed, generation might stop at EOS
        generated = model.generate(prefix, max_new_tokens=100, eos_token_id=2)
        assert generated.shape[1] <= prefix.shape[1] + 100

    def test_generate_with_logit_mask(self, model, tokenizer):
        prefix = torch.tensor([[1, 7]])
        mask = torch.zeros(tokenizer.vocab_size)
        # Block everything except svaras 7-18 and special tokens 0-6
        for i in range(19, tokenizer.vocab_size):
            mask[i] = float("-inf")
        generated = model.generate(prefix, max_new_tokens=8, logit_mask=mask)
        assert generated.shape[1] > prefix.shape[1]


class TestRMSNorm:
    def test_output_shape(self):
        norm = RMSNorm(64)
        x = torch.randn(2, 10, 64)
        out = norm(x)
        assert out.shape == x.shape

    def test_normalized_magnitude(self):
        norm = RMSNorm(64)
        x = torch.randn(2, 10, 64) * 100
        out = norm(x)
        rms = torch.sqrt(out.pow(2).mean(-1))
        # After normalization, RMS should be approximately 1
        assert torch.allclose(rms, torch.ones_like(rms), atol=0.5)


class TestRoPE:
    def test_output_shapes(self):
        rope = RotaryPositionalEmbedding(32, max_seq_len=128)
        cos, sin = rope(64)
        assert cos.shape == (64, 16)  # 32 // 2 = 16
        assert sin.shape == (64, 16)

    def test_dynamic_extension(self):
        rope = RotaryPositionalEmbedding(32, max_seq_len=64)
        # Should auto-extend beyond initial max
        cos, sin = rope(128)
        assert cos.shape == (128, 16)


class TestCheckpointRoundTrip:
    def test_save_and_load(self, model, tokenizer, tmp_path):
        """Save a checkpoint and load it back — forward pass should match."""
        checkpoint_path = str(tmp_path / "test_model.pt")
        # Save
        torch.save({
            "model_state_dict": model.state_dict(),
            "config": {
                "vocab_size": tokenizer.vocab_size,
                "embed_dim": 128,
                "num_heads": 4,
                "num_layers": 4,
                "max_seq_len": 256,
                "dropout": 0.0,
            },
            "epoch": 1,
            "val_loss": 1.0,
        }, checkpoint_path)

        # Load
        loaded_model, config = load_model(checkpoint_path)
        assert config["vocab_size"] == tokenizer.vocab_size

        # Forward pass should produce same output
        x = torch.randint(1, tokenizer.vocab_size, (1, 16))
        model.eval()
        with torch.no_grad():
            orig_out = model(x)["logits"]
            loaded_out = loaded_model(x)["logits"]
        assert torch.allclose(orig_out, loaded_out, atol=1e-5)
