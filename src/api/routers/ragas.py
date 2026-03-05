"""Raga listing and detail endpoints."""

from fastapi import APIRouter, HTTPException, Depends

from src.api.schemas.raga import RagaResponse, RagaListResponse
from src.api.dependencies import get_raga_engine
from src.constraint_engine.raga_engine import RagaEngine

router = APIRouter()


@router.get("", response_model=RagaListResponse)
async def list_ragas(
    melakarta_only: bool = False,
    raga_engine: RagaEngine = Depends(get_raga_engine),
):
    """List all supported ragas."""
    all_ragas = raga_engine.list_ragas()
    if melakarta_only:
        all_ragas = [r for r in all_ragas if r.melakarta_number is not None]

    raga_responses = [
        RagaResponse(
            id=r.id,
            name_english=r.name_english,
            name_telugu=r.name_telugu or "",
            melakarta_number=r.melakarta_number,
            arohanam=r.arohanam,
            avarohanam=r.avarohanam,
            varja_svaras=r.varja_svaras,
            characteristic_phrases=r.characteristic_phrases,
            janya_of=r.janya_of,
            rasa_tags=r.rasa_tags,
        )
        for r in all_ragas
    ]

    return RagaListResponse(ragas=raga_responses, total=len(raga_responses))


@router.get("/{raga_id}", response_model=RagaResponse)
async def get_raga(
    raga_id: str,
    raga_engine: RagaEngine = Depends(get_raga_engine),
):
    """Get detailed information about a specific raga."""
    raga = raga_engine.get_raga(raga_id)
    if not raga:
        raise HTTPException(404, f"Raga '{raga_id}' not found")

    return RagaResponse(
        id=raga.id,
        name_english=raga.name_english,
        name_telugu=raga.name_telugu or "",
        melakarta_number=raga.melakarta_number,
        arohanam=raga.arohanam,
        avarohanam=raga.avarohanam,
        varja_svaras=raga.varja_svaras,
        characteristic_phrases=raga.characteristic_phrases,
        janya_of=raga.janya_of,
        rasa_tags=raga.rasa_tags,
    )
