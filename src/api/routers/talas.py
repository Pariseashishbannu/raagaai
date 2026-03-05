"""Tala listing endpoints."""

from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas.tala import TalaResponse, TalaListResponse
from src.api.dependencies import get_tala_engine
from src.constraint_engine.tala_engine import TalaEngine

router = APIRouter()


@router.get("", response_model=TalaListResponse)
async def list_talas(
    tala_engine: TalaEngine = Depends(get_tala_engine),
):
    """List all supported talas."""
    talas = tala_engine.list_talas()
    tala_responses = [
        TalaResponse(
            id=t.id,
            name=t.name,
            beats=t.beats,
            jathi=t.jathi,
            structure=t.structure,
        )
        for t in talas
    ]
    return TalaListResponse(talas=tala_responses, total=len(tala_responses))


@router.get("/{tala_id}", response_model=TalaResponse)
async def get_tala(
    tala_id: str,
    tala_engine: TalaEngine = Depends(get_tala_engine),
):
    """Get details for a specific tala."""
    tala = tala_engine.get_tala(tala_id)
    if not tala:
        raise HTTPException(404, f"Tala '{tala_id}' not found")

    return TalaResponse(
        id=tala.id,
        name=tala.name,
        beats=tala.beats,
        jathi=tala.jathi,
        structure=tala.structure,
    )
