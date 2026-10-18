"""Request/response schemas for generation endpoints."""

from pydantic import BaseModel, Field
from enum import Enum


class Kala(str, Enum):
    VILAMBA = "vilamba"
    MADHYAMA = "madhyama"
    DRUTA = "druta"


class GenerationRequest(BaseModel):
    prompt: str | None = Field(default=None, examples=["romantic Telugu love song in Mohanam"])
    raga_id: str = Field(default="mohanam", examples=["shankarabharanam"])
    tala_id: str = Field(default="adi", examples=["adi"])
    kala: Kala = Field(default=Kala.MADHYAMA)
    language: str = Field(default="telugu", pattern="^(telugu|tamil|kannada)$")
    theme: str | None = Field(default=None, examples=["devotional"])
    include_chittaswaram: bool = Field(default=False)
    sections: int = Field(default=3, ge=1, le=5, description="Number of charanams")
    structure: str = Field(default="song", pattern="^(traditional|song)$")
    realistic: bool = Field(default=True, description="Re-perform with ACE-Step vocals")
    voice: str = Field(default="female", pattern="^(female|male)$")
    cover_strength: float = Field(
        default=0.7, ge=0.3, le=0.95,
        description="How closely the performance follows the raga guide melody",
    )


class GenerationResponse(BaseModel):
    job_id: str
    status: str
    estimated_wait: int
    created_at: str


class CompositionResult(BaseModel):
    audio_url: str
    song_title: str | None = None
    sahityam: str | None = None
    sahityam_sections: dict | None = None
    svara_sequence: list[str] | None = None
    metadata: dict | None = None
    guide_audio_url: str | None = None
    raga_score: float | None = None


class JobStatus(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    progress: float | None = None
    result: CompositionResult | None = None
    error: str | None = None
