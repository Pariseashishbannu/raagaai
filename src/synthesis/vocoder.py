"""WaveRNN neural vocoder for natural vocal re-synthesis.

Takes additive synth output, extracts mel spectrogram, and reconstructs
a natural-sounding waveform via pretrained WaveRNN vocoder (torchaudio).
"""

import numpy as np
import structlog

from src.core.exceptions import VocoderError

logger = structlog.get_logger()

# Lazy torch imports — never fail at module load
_HAS_TORCH = False
try:
    import torch
    import torchaudio
    _HAS_TORCH = True
except ImportError:
    pass

# Singleton model cache
_model = None
_model_sr = 22050
_hop_length = 275

# Processing config
CHUNK_SECONDS = 10
CROSSFADE_SECONDS = 0.05


def is_available() -> bool:
    """Check if torch + torchaudio are installed."""
    return _HAS_TORCH


def _load_model():
    """Load WaveRNN vocoder (singleton, auto GPU/CPU)."""
    global _model, _model_sr, _hop_length

    if _model is not None:
        return _model, _model_sr

    if not _HAS_TORCH:
        raise VocoderError(
            "torch/torchaudio not installed — install with: pip install raaga-ai[neural]"
        )

    logger.info("vocoder.loading_model")
    bundle = torchaudio.pipelines.TACOTRON2_WAVERNN_CHAR_LJSPEECH
    _model_sr = 22050
    _hop_length = 275

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model = bundle.get_vocoder().to(device).eval()

    logger.info("vocoder.model_loaded", device=str(device), model_sr=_model_sr)
    return _model, _model_sr


def waveform_to_mel(waveform: np.ndarray, source_sr: int) -> "torch.Tensor":
    """Convert waveform to 80-band log-mel spectrogram matching WaveRNN expectations."""
    model, model_sr = _load_model()
    device = next(model.parameters()).device

    wav_tensor = torch.from_numpy(waveform.astype(np.float32)).unsqueeze(0)

    # Resample to model's expected sample rate
    if source_sr != model_sr:
        wav_tensor = torchaudio.functional.resample(wav_tensor, source_sr, model_sr)

    wav_tensor = wav_tensor.to(device)

    # Mel spectrogram with WaveRNN compatible params
    n_fft = 2048
    n_mels = 80

    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=model_sr,
        n_fft=n_fft,
        hop_length=_hop_length,
        n_mels=n_mels,
        f_min=0.0,
        f_max=8000.0,
        power=1.0,
        norm="slaney",
        mel_scale="slaney",
    ).to(device)

    mel = mel_transform(wav_tensor)

    # Log scale with floor to prevent -inf
    mel = torch.clamp(mel, min=1e-5).log()

    return mel


def vocode(mel: "torch.Tensor") -> "torch.Tensor":
    """Run WaveRNN inference on mel spectrogram."""
    model, _ = _load_model()

    with torch.no_grad():
        waveform, _ = model(mel)

    return waveform.squeeze(0)


def enhance_vocal(
    waveform: np.ndarray,
    source_sr: int = 44100,
    target_sr: int = 44100,
) -> np.ndarray:
    """Full vocoder pipeline: waveform -> mel -> WaveRNN -> resample back.

    Processes in chunks with crossfade to manage memory on long compositions.
    """
    if not _HAS_TORCH:
        raise VocoderError("torch/torchaudio not installed")

    logger.info("synthesis.vocoder_start", length=len(waveform), source_sr=source_sr)

    _, model_sr = _load_model()

    chunk_samples = CHUNK_SECONDS * source_sr
    crossfade_samples = int(CROSSFADE_SECONDS * target_sr)

    # Short waveforms — process in one pass
    if len(waveform) <= chunk_samples:
        result = _process_chunk(waveform, source_sr, target_sr)
        logger.info("synthesis.vocoder_done", output_length=len(result))
        return result

    # Chunked processing with crossfade
    output_parts: list[np.ndarray] = []
    pos = 0

    while pos < len(waveform):
        end = min(pos + chunk_samples, len(waveform))
        chunk = waveform[pos:end]

        processed = _process_chunk(chunk, source_sr, target_sr)

        if output_parts and crossfade_samples > 0 and len(processed) > crossfade_samples:
            prev = output_parts[-1]
            if len(prev) >= crossfade_samples:
                # Crossfade overlap
                fade_out = np.linspace(1.0, 0.0, crossfade_samples)
                fade_in = np.linspace(0.0, 1.0, crossfade_samples)

                prev[-crossfade_samples:] *= fade_out
                processed[:crossfade_samples] *= fade_in
                prev[-crossfade_samples:] += processed[:crossfade_samples]

                output_parts.append(processed[crossfade_samples:])
            else:
                output_parts.append(processed)
        else:
            output_parts.append(processed)

        pos = end

    result = np.concatenate(output_parts) if output_parts else np.array([], dtype=np.float32)
    logger.info("synthesis.vocoder_done", output_length=len(result))
    return result


def _process_chunk(
    chunk: np.ndarray,
    source_sr: int,
    target_sr: int,
) -> np.ndarray:
    """Process a single chunk through the vocoder."""
    mel = waveform_to_mel(chunk, source_sr)
    vocoded = vocode(mel)

    # Move to CPU numpy
    result = vocoded.cpu().numpy()

    # Resample from model sr back to target
    _, model_sr = _load_model()
    if model_sr != target_sr:
        result_tensor = torch.from_numpy(result).unsqueeze(0)
        result_tensor = torchaudio.functional.resample(result_tensor, model_sr, target_sr)
        result = result_tensor.squeeze(0).numpy()

    return result
