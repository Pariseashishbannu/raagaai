"""Composition API schemas."""

from pydantic import BaseModel


class CompositionResponse(BaseModel):
    id: str
    raga_id: str
    tala_id: str
    audio_url: str | None = None
    sahityam: str | None = None
    svara_sequence: list[str] | None = None
    duration_seconds: int | None = None
    is_public: bool = False
    created_at: str | None = None

    model_config = {"from_attributes": True}


class CompositionListResponse(BaseModel):
    compositions: list[CompositionResponse]
    total: int
