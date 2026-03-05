"""Raga API schemas."""

from pydantic import BaseModel


class RagaResponse(BaseModel):
    id: str
    name_english: str
    name_telugu: str | None = None
    melakarta_number: int | None = None
    arohanam: list[str]
    avarohanam: list[str]
    varja_svaras: list[str] = []
    characteristic_phrases: list[list[str]] = []
    janya_of: str | None = None
    rasa_tags: list[str] = []

    model_config = {"from_attributes": True}


class RagaListResponse(BaseModel):
    ragas: list[RagaResponse]
    total: int
