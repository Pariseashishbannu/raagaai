"""Realistic performance of a composition via an ACE-Step 1.5 API server.

Raaga.AI's synth renders a raga-correct guide track; ACE-Step's ``cover`` task
re-performs it with real-sounding vocals and instruments, singing our lyrics.
Each candidate is pitch-tracked and the most raga-faithful one wins.

The server is reached over HTTP only (``ACESTEP_API_URL``), so this module needs no
torch/GPU. Run ``acestep-api`` locally or in Colab (notebooks/acestep_server_colab.ipynb).
"""

import io
import json
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx
import soundfile as sf
import structlog

from src.api.config import settings
from src.constraint_engine.raga_engine import RagaSpec
from src.constraint_engine.tala_engine import TalaSpec
from src.core.constants import DEFAULT_TONIC_HZ, KALA_BPM, Kala
from src.synthesis.pipeline import song_arrangement
from src.synthesis.raga_adherence import raga_pitch_classes, score_audio

logger = structlog.get_logger()

# ACE-Step structure tags for each song-mode segment
SEGMENT_TAGS = {
    "intro": "[intro]",
    "pallavi": "[verse]",
    "anupallavi": "[chorus]",
    "charanam": "[verse]",
    "chittaswaram": "[bridge]",
    "outro": "[outro]",
}

RASA_MOODS = {
    "shringara": "romantic", "karuna": "tender, compassionate", "bhakti": "devotional",
    "shanta": "peaceful, meditative", "veera": "heroic, majestic", "hasya": "joyful",
    "adbhuta": "wondrous", "raudra": "intense", "bhayanaka": "dark, tense",
}

LANGUAGE_CODES = {"telugu": "te", "tamil": "ta", "kannada": "unknown"}

POLL_INTERVAL_S = 3.0


class AceStepError(Exception):
    pass


@dataclass
class PerformedSong:
    wav_bytes: bytes
    duration_seconds: int
    raga_score: float
    guide_raga_score: float
    candidate_scores: list[float]
    seed: str | None
    caption: str
    lyrics: str


def build_lyric_sheet(svara_sections: dict[str, list[str]], lyrics: dict[str, str]) -> str:
    """Lyrics in the exact order the guide track performs the sections."""
    lines: list[str] = []
    for label, key in song_arrangement(svara_sections):
        lines.append(SEGMENT_TAGS.get(label, "[verse]"))
        if label not in ("intro", "outro") and lyrics.get(key):
            lines.append(lyrics[key])
        lines.append("")
    return "\n".join(lines).strip()


def build_caption(
    raga: RagaSpec, tala: TalaSpec, kala: str, theme: str | None, voice: str, extra: str = ""
) -> str:
    moods = [RASA_MOODS[r] for r in raga.rasa_tags if r in RASA_MOODS]
    if theme:
        moods.insert(0, theme)
    moods = list(dict.fromkeys(moods))  # theme often repeats a rasa mood
    parts = [
        f"Carnatic classical song in raga {raga.name_english}, {tala.name} tala, {kala} tempo",
        ", ".join(moods),
        f"expressive {voice} Indian classical vocals with gamakas",
        "violin, veena, bamboo flute, mridangam, tanpura drone",
        "warm studio production",
        extra,
    ]
    return ", ".join(p for p in parts if p)[:512]


class AceStepClient:
    """Minimal client for the ACE-Step 1.5 REST API (release_task / query_result)."""

    def __init__(self, base_url: str, api_key: str = "", transport: httpx.BaseTransport | None = None):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=120.0, transport=transport,
        )

    def submit_cover(
        self, guide_wav: bytes, *, prompt: str, lyrics: str, language: str,
        bpm: int, strength: float, candidates: int,
        model: str = "", inference_steps: int = 0, guidance_scale: float = 0.0,
    ) -> str:
        form = {
            "task_type": "cover",
            "prompt": prompt,
            "lyrics": lyrics,
            "vocal_language": language,
            "bpm": str(bpm),
            "audio_cover_strength": str(strength),
            "batch_size": str(max(1, min(candidates, 8))),
            "audio_format": "wav",
            "thinking": "false",
        }
        # Empty/zero = let the server use the model it was started with and its defaults
        if model:
            form["model"] = model
        if inference_steps:
            form["inference_steps"] = str(inference_steps)
        if guidance_scale:
            form["guidance_scale"] = str(guidance_scale)
        resp = self._http.post(
            "/release_task", data=form,
            files={"src_audio": ("guide.wav", guide_wav, "audio/wav")},
        )
        task_id = (self._unwrap(resp) or {}).get("task_id")
        if not task_id:
            raise AceStepError(f"no task_id in release_task response: {resp.text[:200]}")
        return task_id

    def wait(self, task_id: str, timeout_s: float) -> list[dict]:
        """Poll until the task finishes; returns its per-audio result entries."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            resp = self._http.post("/query_result", json={"task_id_list": [task_id]})
            items = self._unwrap(resp) or []
            item = next((i for i in items if i.get("task_id") == task_id), None)
            if item and item.get("status") == 1:
                result = item.get("result") or "[]"
                return json.loads(result) if isinstance(result, str) else result
            if item and item.get("status") == 2:
                raise AceStepError(f"ACE-Step task {task_id} failed")
            time.sleep(POLL_INTERVAL_S)
        raise AceStepError(f"ACE-Step task {task_id} timed out after {timeout_s:.0f}s")

    def download(self, file_ref: str) -> bytes:
        # Results give either a ready /v1/audio URL or a server-side path
        url = file_ref if file_ref.startswith("/v1/audio") else f"/v1/audio?path={quote(file_ref)}"
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _unwrap(resp: httpx.Response):
        resp.raise_for_status()
        body = resp.json()
        if body.get("code", 200) != 200 or body.get("error"):
            raise AceStepError(f"ACE-Step error: {body.get('error')}")
        return body.get("data")


def perform_song(
    guide_wav: bytes,
    svara_sections: dict[str, list[str]],
    lyrics_sections: dict[str, str],
    raga: RagaSpec,
    tala: TalaSpec,
    kala: str = "madhyama",
    theme: str | None = None,
    language: str = "telugu",
    voice: str = "female",
    strength: float = 0.7,
    candidates: int | None = None,
    style: str = "",
    client: AceStepClient | None = None,
) -> PerformedSong | None:
    """Re-perform the guide track with ACE-Step; None if unavailable or it failed.

    Never raises for server problems — callers fall back to the guide synth audio.
    """
    if client is None:
        if not settings.ACESTEP_API_URL:
            return None
        client = AceStepClient(settings.ACESTEP_API_URL, settings.ACESTEP_API_KEY)
    candidates = candidates or settings.ACESTEP_CANDIDATES

    lyrics = build_lyric_sheet(svara_sections, lyrics_sections)
    caption = build_caption(raga, tala, kala, theme, voice, style)
    allowed = raga_pitch_classes(raga.arohanam, raga.avarohanam)

    try:
        task_id = client.submit_cover(
            guide_wav, prompt=caption, lyrics=lyrics,
            language=LANGUAGE_CODES.get(language, "unknown"),
            bpm=KALA_BPM.get(Kala(kala), 100), strength=strength, candidates=candidates,
            model=settings.ACESTEP_MODEL,
            inference_steps=settings.ACESTEP_INFERENCE_STEPS,
            guidance_scale=settings.ACESTEP_GUIDANCE_SCALE,
        )
        logger.info("performer.submitted", task_id=task_id, candidates=candidates,
                    model=settings.ACESTEP_MODEL)
        entries = client.wait(task_id, settings.ACESTEP_TIMEOUT_S)
        files = [e["file"] for e in entries if e.get("file")]
        if not files:
            raise AceStepError("task succeeded but returned no audio")
        seeds = (entries[0].get("seed_value") or "").split(",")
        scored = []
        for idx, f in enumerate(files):
            audio, sr = sf.read(io.BytesIO(client.download(f)), always_2d=True)
            rep = score_audio(audio.T, sr, allowed, DEFAULT_TONIC_HZ)
            scored.append((rep.score, idx, audio, sr))
            logger.info("performer.candidate", idx=idx, raga_score=round(rep.score, 3))
    except (httpx.HTTPError, AceStepError, ValueError, KeyError, RuntimeError) as e:
        logger.warning("performer.failed", error=str(e))
        return None

    guide_audio, guide_sr = sf.read(io.BytesIO(guide_wav))
    guide_score = score_audio(guide_audio, guide_sr, allowed, DEFAULT_TONIC_HZ).score

    scored.sort(key=lambda s: s[0], reverse=True)
    best_score, best_idx, audio, sr = scored[0]
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return PerformedSong(
        wav_bytes=buf.getvalue(),
        duration_seconds=int(len(audio) / sr),
        raga_score=round(best_score, 3),
        guide_raga_score=round(guide_score, 3),
        candidate_scores=[round(s[0], 3) for s in scored],
        seed=seeds[best_idx].strip() if best_idx < len(seeds) else None,
        caption=caption,
        lyrics=lyrics,
    )
