import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.modules.identity import schemas, service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships import service as memberships_service
from app.modules.memberships.models import Membership
from app.modules.organizations.schemas import MembershipResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: schemas.RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    user = await service.register_user(db, email=body.email, password=body.password)
    await db.commit()
    return user


@router.post("/login", response_model=schemas.TokenPair)
async def login(
    body: schemas.LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.TokenPair:
    user = await service.authenticate_user(db, email=body.email, password=body.password)
    access_token, refresh_token = await service.issue_token_pair(
        db,
        user=user,
        device_label=request.headers.get("User-Agent"),
        ip_address=_client_ip(request),
    )
    await db.commit()
    return schemas.TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=schemas.TokenPair)
async def refresh(
    body: schemas.RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
) -> schemas.TokenPair:
    access_token, refresh_token = await service.refresh_token_pair(
        db, refresh_token=body.refresh_token
    )
    await db.commit()
    return schemas.TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: schemas.RefreshRequest,
    db: AsyncSession = Depends(get_db_session),
    _current_user: User = Depends(get_current_user),
) -> None:
    await service.revoke_session_by_token(db, refresh_token=body.refresh_token)
    await db.commit()


@router.get("/sessions", response_model=list[schemas.SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.SessionResponse]:
    sessions = await service.list_active_sessions(db, user_id=current_user.id)
    return [schemas.SessionResponse.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    await service.revoke_session(db, user_id=current_user.id, session_id=session_id)
    await db.commit()


@router.get("/me", response_model=schemas.UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/me/roles", response_model=list[MembershipResponse])
async def get_my_roles(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[Membership]:
    """The caller's own active roles. Used by clients to decide what to show, never to enforce."""
    return await memberships_service.list_active_memberships(db, user_id=current_user.id)
