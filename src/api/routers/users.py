"""User registration and authentication endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse,
    RefreshRequest,
)
from src.api.middleware.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from src.db.session import get_session
from src.db.models.user import User

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    req: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user."""
    # Check if email already exists
    result = await session.execute(select(User).where(User.email == req.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Email already registered")

    user = User(
        id=uuid.uuid4(),
        email=req.email,
        hashed_password=hash_password(req.password),
        tier="free",
        monthly_generations_used=0,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse(
        id=str(user.id),
        email=user.email,
        tier=user.tier,
        monthly_generations_used=user.monthly_generations_used,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate and get JWT tokens."""
    result = await session.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.tier),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    req: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """Refresh an access token."""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")

    user_id = payload["sub"]
    user = await session.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(401, "User not found")

    return TokenResponse(
        access_token=create_access_token(str(user.id), user.tier),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserResponse)
async def get_profile(
    user_info: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user profile."""
    user = await session.get(User, uuid.UUID(user_info["user_id"]))
    if not user:
        raise HTTPException(404, "User not found")

    return UserResponse(
        id=str(user.id),
        email=user.email,
        tier=user.tier,
        monthly_generations_used=user.monthly_generations_used,
    )
