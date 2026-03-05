"""Unit tests for the svara tokenizer."""

from src.ml.tokenizer import SvaraTokenizer


def test_encode_decode_roundtrip():
    """Encoding then decoding should return original svaras."""
    tok = SvaraTokenizer()
    svaras = ["Sa", "Ri2", "Ga2", "Pa"]
    encoded = tok.encode(svaras)
    decoded = tok.decode(encoded)
    assert decoded == svaras


def test_vocab_size():
    """Vocab should have expected size."""
    tok = SvaraTokenizer()
    assert tok.vocab_size > 20


def test_encode_conditioning():
    """Conditioning should produce a valid token sequence."""
    tok = SvaraTokenizer()
    ids = tok.encode_conditioning("mohanam", "adi", "pallavi", "madhyama")
    assert len(ids) > 0
    assert all(isinstance(i, int) for i in ids)
