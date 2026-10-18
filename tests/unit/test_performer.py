"""Tests for the ACE-Step performer, against a mocked ACE-Step API server."""

import io
import json

import httpx
import numpy as np
import pytest
import soundfile as sf

from src.constraint_engine.raga_engine import RagaEngine
from src.constraint_engine.tala_engine import TalaEngine
from src.core.constants import DEFAULT_TONIC_HZ
from src.synthesis import performer
from src.synthesis.performer import AceStepClient, build_lyric_sheet, perform_song

SR = 22050


def _tone_wav(semitones: list[int], note_s: float = 0.4) -> bytes:
    """A melody of pure tones at the given semitones above the default tonic."""
    t = np.arange(int(SR * note_s)) / SR
    y = np.concatenate([
        0.5 * np.sin(2 * np.pi * DEFAULT_TONIC_HZ * 2 ** (st / 12) * t) for st in semitones
    ])
    buf = io.BytesIO()
    sf.write(buf, y, SR, format="WAV")
    return buf.getvalue()


MOHANAM_TUNE = [0, 2, 4, 7, 9, 7, 4, 2] * 2         # all inside mohanam
OFF_RAGA_TUNE = [0, 1, 3, 5, 6, 8, 10, 11] * 2       # mostly outside it


def _mock_server(candidates: list[bytes], fail: bool = False, polls_before_done: int = 1):
    state = {"polls": 0, "submitted": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/release_task":
            state["submitted"] = request
            return httpx.Response(200, json={"data": {"task_id": "t1"}, "code": 200})
        if request.url.path == "/query_result":
            state["polls"] += 1
            if state["polls"] <= polls_before_done:
                status, result = 0, None
            else:
                status = 2 if fail else 1
                result = json.dumps([
                    {"file": f"/tmp/api_audio/c{i}.wav", "seed_value": "11,22,33"}
                    for i in range(len(candidates))
                ])
            return httpx.Response(200, json={
                "data": [{"task_id": "t1", "status": status, "result": result}], "code": 200,
            })
        if request.url.path == "/v1/audio":
            idx = int(request.url.params["path"].split("/c")[-1].split(".")[0])
            return httpx.Response(200, content=candidates[idx])
        return httpx.Response(404)

    return httpx.MockTransport(handler), state


@pytest.fixture
def song_inputs():
    raga = RagaEngine().get_raga("mohanam")
    tala = TalaEngine().get_tala("adi")
    svara_sections = {"pallavi": ["Sa", "Ri2"], "anupallavi": ["Ga2"], "charanam": ["Pa"]}
    lyrics = {"pallavi": "pallavi words", "anupallavi": "chorus words", "charanam": "verse two"}
    return raga, tala, svara_sections, lyrics


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(performer, "POLL_INTERVAL_S", 0.0)


def test_lyric_sheet_follows_song_arrangement(song_inputs):
    _, _, svara_sections, lyrics = song_inputs
    sheet = build_lyric_sheet(svara_sections, lyrics)
    tags = [line for line in sheet.splitlines() if line.startswith("[")]
    assert tags[0] == "[intro]" and tags[-1] == "[outro]"
    assert sheet.count("chorus words") == 3   # anupallavi is the repeated hook
    assert sheet.index("pallavi words") < sheet.index("chorus words") < sheet.index("verse two")


def test_picks_most_raga_faithful_candidate(song_inputs):
    raga, tala, svara_sections, lyrics = song_inputs
    transport, state = _mock_server([_tone_wav(OFF_RAGA_TUNE), _tone_wav(MOHANAM_TUNE)])
    client = AceStepClient("http://ace", api_key="k", transport=transport)

    song = perform_song(
        _tone_wav(MOHANAM_TUNE), svara_sections, lyrics, raga, tala,
        candidates=2, client=client,
    )

    assert song is not None
    assert song.raga_score > 0.8      # pyin smears note transitions, so <1.0
    assert song.candidate_scores[0] > song.candidate_scores[1]
    assert song.seed == "22"          # seed of the winning (second) candidate
    req = state["submitted"]
    assert req.headers["authorization"] == "Bearer k"
    body = req.content.decode(errors="ignore")
    assert 'name="task_type"' in body and "cover" in body
    assert 'name="src_audio"; filename="guide.wav"' in body
    assert "acestep-v15-base" in body   # demo uses the base model by default


def test_failed_task_falls_back(song_inputs):
    raga, tala, svara_sections, lyrics = song_inputs
    transport, _ = _mock_server([_tone_wav(MOHANAM_TUNE)], fail=True)
    client = AceStepClient("http://ace", transport=transport)
    assert perform_song(_tone_wav(MOHANAM_TUNE), svara_sections, lyrics, raga, tala,
                        client=client) is None


def test_timeout_falls_back(song_inputs, monkeypatch):
    raga, tala, svara_sections, lyrics = song_inputs
    monkeypatch.setattr(performer.settings, "ACESTEP_TIMEOUT_S", 0)
    transport, _ = _mock_server([_tone_wav(MOHANAM_TUNE)], polls_before_done=10**6)
    client = AceStepClient("http://ace", transport=transport)
    assert perform_song(_tone_wav(MOHANAM_TUNE), svara_sections, lyrics, raga, tala,
                        client=client) is None


def test_unconfigured_returns_none(song_inputs, monkeypatch):
    raga, tala, svara_sections, lyrics = song_inputs
    monkeypatch.setattr(performer.settings, "ACESTEP_API_URL", "")
    assert perform_song(b"", svara_sections, lyrics, raga, tala) is None
