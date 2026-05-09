"""Custom exception hierarchy for Raaga.AI."""


class RaagaError(Exception):
    """Base exception for all Raaga.AI errors."""


class RagaValidationError(RaagaError):
    """Svara sequence violates raga constraints."""


class TalaValidationError(RaagaError):
    """Rhythm doesn't align with tala structure."""


class GenerationError(RaagaError):
    """Error during composition generation pipeline."""


class SynthesisError(RaagaError):
    """Error during audio synthesis."""


class VocoderError(SynthesisError):
    """Error in neural vocoder processing."""


class SahityamError(RaagaError):
    """Error during lyric generation."""


class AuthenticationError(RaagaError):
    """Authentication failure."""


class AuthorizationError(RaagaError):
    """User lacks permission for requested action."""


class RateLimitError(RaagaError):
    """User has exceeded their rate limit."""


class StorageError(RaagaError):
    """Error interacting with object storage."""


class JobNotFoundError(RaagaError):
    """Requested job does not exist."""
