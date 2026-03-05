"""Composition CRUD endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.composition import CompositionResponse, CompositionListResponse
from src.api.middleware.auth import get_current_user
from src.db.session import get_session
from src.db.repositories.composition_repo import CompositionRepository

router = APIRouter()


@router.get("", response_model=CompositionListResponse)
async def list_compositions(
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List current user's saved compositions."""
    repo = CompositionRepository(session)
    compositions = await repo.get_by_user(user["user_id"])
    return CompositionListResponse(
        compositions=[
            CompositionResponse(
                id=str(c.id),
                raga_id=c.raga_id,
                tala_id=c.tala_id,
                sahityam=c.sahityam,
                svara_sequence=c.svara_sequence,
                duration_seconds=c.duration_seconds,
                is_public=c.is_public,
                created_at=str(c.created_at) if c.created_at else None,
            )
            for c in compositions
        ],
        total=len(compositions),
    )


@router.get("/{composition_id}", response_model=CompositionResponse)
async def get_composition(
    composition_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific composition with download links."""
    repo = CompositionRepository(session)
    comp = await repo.get_by_id(composition_id)
    if not comp:
        raise HTTPException(404, "Composition not found")

    audio_url = None
    if comp.audio_key:
        try:
            from src.storage.client import get_presigned_url
            from src.api.config import settings
            audio_url = get_presigned_url(settings.MINIO_BUCKET_AUDIO, comp.audio_key)
        except Exception:
            audio_url = None

    return CompositionResponse(
        id=str(comp.id),
        raga_id=comp.raga_id,
        tala_id=comp.tala_id,
        audio_url=audio_url,
        sahityam=comp.sahityam,
        svara_sequence=comp.svara_sequence,
        duration_seconds=comp.duration_seconds,
        is_public=comp.is_public,
        created_at=str(comp.created_at) if comp.created_at else None,
    )


@router.delete("/{composition_id}")
async def delete_composition(
    composition_id: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a composition."""
    repo = CompositionRepository(session)
    deleted = await repo.delete_by_id(composition_id)
    if not deleted:
        raise HTTPException(404, "Composition not found")
    return {"status": "deleted", "id": composition_id}
