"""Pydantic schemas for Carnatic song generation."""

from typing import Literal
from pydantic import BaseModel, Field


class SongGenerationRequest(BaseModel):
    raga_id: str = "mohanam"
    tala_id: str = "adi"
    kala: Literal["vilamba", "madhyama", "druta"] = "madhyama"
    theme: Literal["devotional", "romantic", "nature", "celebration", "melancholy"] = "devotional"
    sections: int = Field(default=3, ge=1, le=5, description="Number of charanams")
    language: str = "telugu"
    prompt: str | None = None


class SongGenerationResponse(BaseModel):
    job_id: str
    status: str
    estimated_wait: int
    created_at: str


class SongResult(BaseModel):
    audio_url: str
    song_title: str | None
    sahityam: str | None
    sahityam_sections: dict | None
    svara_sequence: list[str] | None
    metadata: dict | None


class SongJobStatus(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    progress: float | None = None
    result: SongResult | None = None
    error: str | None = None
