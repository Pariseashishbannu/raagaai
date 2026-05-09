"""Audio export utilities — WAV/MP3 conversion."""

import io


def wav_to_mp3(wav_bytes: bytes) -> bytes:
    """Convert WAV bytes to MP3 using pydub (requires ffmpeg)."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(io.BytesIO(wav_bytes))
        mp3_buffer = io.BytesIO()
        audio.export(mp3_buffer, format="mp3", bitrate="192k")
        return mp3_buffer.getvalue()
    except Exception:
        # ffmpeg not available — return WAV as fallback
        return wav_bytes
