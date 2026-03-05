"""Tala API schemas."""

from pydantic import BaseModel


class TalaResponse(BaseModel):
    id: str
    name: str
    beats: int
    jathi: str
    structure: list[str]

    model_config = {"from_attributes": True}


class TalaListResponse(BaseModel):
    talas: list[TalaResponse]
    total: int
