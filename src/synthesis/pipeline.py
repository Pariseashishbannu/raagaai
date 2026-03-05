"""Full audio synthesis pipeline — orchestrates melody + percussion + bass + drone + mix."""

import io

import numpy as np
import soundfile as sf
import structlog

from src.synthesis.gamaka_renderer import GamakaRenderer, svara_to_hz
from src.synthesis.vocal_synth import VocalSynthesizer
from src.synthesis.tambura import generate_tambura_drone
from src.synthesis.percussion import PercussionSynthesizer
from src.synthesis.bass import BassLayer
from src.synthesis import vocoder
from src.api.config import settings
from src.core.constants import DEFAULT_TONIC_HZ, Kala, KALA_BPM

logger = structlog.get_logger()

# Volume curves per section type (relative gain)
SECTION_DYNAMICS = {
    "intro": 0.55,
    "pallavi": 0.80,
    "anupallavi": 0.95,
    "charanam": 0.85,
    "chittaswaram": 0.90,
    "outro": 0.50,
}

# Inter-section pause duration in seconds
SECTION_PAUSE = 0.5


class AudioOutput:
    def __init__(self, wav_bytes: bytes, duration_seconds: int, sample_rate: int,
                 svara_sequence: list[str]):
        self.wav_bytes = wav_bytes
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.svara_sequence = svara_sequence


class SynthesisPipeline:
    def __init__(self):
        self.gamaka_renderer = GamakaRenderer()
        self.vocal_synth = VocalSynthesizer()
        self.percussion = PercussionSynthesizer()
        self.bass = BassLayer()
        self.use_vocoder = vocoder.is_available() and settings.VOCODER_ENABLED

    def render(
        self,
        svara_sections: dict[str, list[str]],
        raga_id: str,
        tala_id: str,
        kala: str = "madhyama",
        tonic_hz: float = DEFAULT_TONIC_HZ,
        sample_rate: int = 44100,
        structure: str = "song",
        use_vocoder: bool | None = None,
    ) -> AudioOutput:
        """
        Full render pipeline:
        1. Arrange sections in performance order
        2. Generate pitch contours with gamakas per section
        3. Apply section-level dynamics (volume curves)
        4. Synthesize vocal track
        5. Generate percussion, bass, and tambura
        6. Mix all layers and export WAV
        """
        bpm = KALA_BPM.get(Kala(kala), 100)
        beat_duration = 60.0 / bpm

        # Build performance order as labeled segments
        if structure == "song":
            segments = self._arrange_sections_song(svara_sections)
        else:
            segments = self._arrange_sections(svara_sections)

        # Render each segment with its own dynamics, inserting pauses between
        all_vocal_parts: list[np.ndarray] = []
        ordered_svaras: list[str] = []
        pause_samples = int(SECTION_PAUSE * sample_rate)

        for seg_idx, (section_label, svaras) in enumerate(segments):
            ordered_svaras.extend(svaras)

            # Pitch contours for this segment
            contours = self.gamaka_renderer.render(
                svaras=svaras,
                raga_id=raga_id,
                kala=kala,
                tonic_hz=tonic_hz,
                beat_duration=beat_duration,
                sample_rate=sample_rate,
            )

            # Synthesize vocal for this segment
            segment_audio = self.vocal_synth.synthesize(contours, sample_rate)

            # Apply section dynamics
            gain = SECTION_DYNAMICS.get(section_label, 0.80)
            segment_audio *= gain

            all_vocal_parts.append(segment_audio)

            # Insert inter-section pause (except after last segment)
            if seg_idx < len(segments) - 1:
                all_vocal_parts.append(np.zeros(pause_samples))

        # Combine all vocal segments
        vocal = np.concatenate(all_vocal_parts) if all_vocal_parts else np.array([])

        # Neural vocoder enhancement — improves vocal naturalness
        should_vocode = use_vocoder if use_vocoder is not None else self.use_vocoder
        if should_vocode and len(vocal) > 0:
            try:
                vocal = vocoder.enhance_vocal(vocal, source_sr=sample_rate, target_sr=sample_rate)
            except Exception:
                logger.warning("synthesis.vocoder_fallback", exc_info=True)

        # Collect training data if enabled
        if settings.COLLECT_TRAINING_DATA and len(vocal) > 0:
            try:
                from src.synthesis.data_collector import save_training_pair
                save_training_pair(
                    job_id=raga_id,
                    vocal_waveform=vocal,
                    pitch_contours=[],
                    metadata={"raga_id": raga_id, "tala_id": tala_id, "kala": kala},
                    sample_rate=sample_rate,
                )
            except Exception:
                logger.warning("synthesis.training_data_failed", exc_info=True)

        total_samples = len(vocal)
        duration_sec = total_samples / sample_rate

        # Generate all layers to match vocal length
        drone = generate_tambura_drone(tonic_hz, duration_sec, sample_rate)
        perc = self.percussion.generate(tala_id, total_samples, kala, sample_rate)
        bass_track = self.bass.generate(
            # Re-render contours for the full ordered svaras for bass reference
            self.gamaka_renderer.render(
                svaras=ordered_svaras,
                raga_id=raga_id,
                kala=kala,
                tonic_hz=tonic_hz,
                beat_duration=beat_duration,
                sample_rate=sample_rate,
            ),
            sample_rate,
        )

        # Match all lengths
        min_len = min(len(vocal), len(drone), len(perc), len(bass_track))
        if min_len == 0:
            min_len = total_samples
        vocal = vocal[:min_len]
        drone = drone[:min_len] if len(drone) >= min_len else np.pad(drone, (0, min_len - len(drone)))
        perc = perc[:min_len] if len(perc) >= min_len else np.pad(perc, (0, min_len - len(perc)))
        bass_track = bass_track[:min_len] if len(bass_track) >= min_len else np.pad(bass_track, (0, min_len - len(bass_track)))

        # Song-like mix: vocal dominant, percussion gives rhythm, bass adds body
        mixed = (
            vocal * 0.45 +
            perc * 0.25 +
            bass_track * 0.18 +
            drone * 0.12
        )

        # Normalize
        peak = np.max(np.abs(mixed))
        if peak > 0:
            mixed = mixed / peak * 0.92

        # Fade in/out
        fade_in = min(int(1.2 * sample_rate), min_len // 6)
        fade_out = min(int(1.5 * sample_rate), min_len // 4)
        if fade_in > 0:
            mixed[:fade_in] *= np.linspace(0, 1, fade_in)
        if fade_out > 0:
            mixed[-fade_out:] *= np.linspace(1, 0, fade_out)

        # Convert to 16-bit PCM
        pcm = (mixed * 32767).astype(np.int16)

        # Export WAV
        wav_buffer = io.BytesIO()
        sf.write(wav_buffer, pcm, sample_rate, format="WAV", subtype="PCM_16")
        wav_bytes = wav_buffer.getvalue()

        return AudioOutput(
            wav_bytes=wav_bytes,
            duration_seconds=int(duration_sec),
            sample_rate=sample_rate,
            svara_sequence=ordered_svaras,
        )

    def _arrange_sections_song(
        self, svara_sections: dict[str, list[str]]
    ) -> list[tuple[str, list[str]]]:
        """Arrange in verse-chorus-verse-chorus song structure with labeled segments."""
        segments: list[tuple[str, list[str]]] = []
        charanams = sorted(k for k in svara_sections if k.startswith("charanam"))

        # Intro — first few notes of pallavi, gentle opening
        if "pallavi" in svara_sections:
            intro = svara_sections["pallavi"][:8]
            segments.append(("intro", intro))

        # Verse 1 (pallavi) — full section
        if "pallavi" in svara_sections:
            segments.append(("pallavi", svara_sections["pallavi"]))

        # Chorus (anupallavi as the hook)
        if "anupallavi" in svara_sections:
            segments.append(("anupallavi", svara_sections["anupallavi"]))

        # Verse 2 (first charanam)
        if charanams:
            segments.append(("charanam", svara_sections[charanams[0]]))

        # Chorus repeat
        if "anupallavi" in svara_sections:
            segments.append(("anupallavi", svara_sections["anupallavi"]))

        # Pallavi reprise — builds familiarity
        if "pallavi" in svara_sections:
            segments.append(("pallavi", svara_sections["pallavi"]))

        # Bridge (second charanam or chittaswaram)
        if len(charanams) > 1:
            segments.append(("charanam", svara_sections[charanams[1]]))
        elif "chittaswaram" in svara_sections:
            segments.append(("chittaswaram", svara_sections["chittaswaram"]))

        # Final chorus
        if "anupallavi" in svara_sections:
            segments.append(("anupallavi", svara_sections["anupallavi"]))

        # Outro — last few pallavi notes fading out
        if "pallavi" in svara_sections:
            outro = svara_sections["pallavi"][-6:]
            segments.append(("outro", outro))

        return segments

    def _arrange_sections(
        self, svara_sections: dict[str, list[str]]
    ) -> list[tuple[str, list[str]]]:
        """Arrange sections in traditional Carnatic performance order."""
        segments: list[tuple[str, list[str]]] = []

        if "pallavi" in svara_sections:
            segments.append(("pallavi", svara_sections["pallavi"]))
            segments.append(("pallavi", svara_sections["pallavi"]))

        if "anupallavi" in svara_sections:
            segments.append(("anupallavi", svara_sections["anupallavi"]))
            segments.append(("anupallavi", svara_sections["anupallavi"]))

        charanam_keys = sorted(k for k in svara_sections if k.startswith("charanam"))
        for ck in charanam_keys:
            segments.append(("charanam", svara_sections[ck]))
            if "pallavi" in svara_sections:
                segments.append(("pallavi", svara_sections["pallavi"]))

        if "chittaswaram" in svara_sections:
            segments.append(("chittaswaram", svara_sections["chittaswaram"]))

        return segments
