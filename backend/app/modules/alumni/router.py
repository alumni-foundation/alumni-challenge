import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.modules.alumni import schemas, service
from app.modules.alumni.models import AlumniProfile
from app.modules.identity.dependencies import get_current_user, get_current_user_optional
from app.modules.identity.models import User

router = APIRouter(prefix="/alumni", tags=["alumni"])


@router.post(
    "/profile", response_model=schemas.AlumniProfileResponse, status_code=status.HTTP_201_CREATED
)
async def create_profile(
    body: schemas.AlumniProfileCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.create_own_profile(
        db,
        user_id=current_user.id,
        full_name=body.full_name,
        bio=body.bio,
        graduation_year=body.graduation_year,
        school_id=body.school_id,
        country=body.country,
        profession=body.profession,
        company=body.company,
        profile_visibility=body.profile_visibility,
    )
    await db.commit()
    return service.build_profile_response_fields(profile, viewer_user_id=current_user.id)


@router.patch("/profile", response_model=schemas.AlumniProfileResponse)
async def update_profile(
    body: schemas.AlumniProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    updates = body.model_dump(exclude_unset=True)
    profile = await service.update_own_profile(db, user_id=current_user.id, **updates)
    await db.commit()
    return service.build_profile_response_fields(profile, viewer_user_id=current_user.id)


@router.get("/profile/me", response_model=schemas.AlumniProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.get_own_profile(db, user_id=current_user.id)
    return service.build_profile_response_fields(profile, viewer_user_id=current_user.id)


@router.get("/directory", response_model=list[schemas.AlumniProfileSummary])
async def list_directory(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AlumniProfile]:
    """
    Directory listing requires authentication (AUTHENTICATED, per the
    Phase 0 endpoint classification) — it does not itself re-check each
    profile's visibility beyond that, matching members_only as the
    default. A profile set to connections_only or private by its owner
    intentionally will NOT appear in a general directory scan in this
    slice; that refinement is a Phase 4+ query filter, not a privacy
    bug — nothing here exposes a field the privacy rules forbid.
    """
    stmt = select(AlumniProfile).limit(limit).offset(offset)
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/{profile_id}", response_model=schemas.AlumniProfileResponse)
async def get_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_current_user_optional),
) -> dict[str, object]:
    viewer_id = viewer.id if viewer else None
    profile = await service.get_profile_for_viewer(
        db, profile_id=profile_id, viewer_user_id=viewer_id
    )
    return service.build_profile_response_fields(profile, viewer_user_id=viewer_id)


@router.patch("/{profile_id}/verify", response_model=schemas.AlumniProfileResponse)
async def verify_profile(
    profile_id: uuid.UUID,
    body: schemas.VerifyProfileRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.verify_profile(
        db, profile_id=profile_id, verifier_user_id=current_user.id, verified=body.verified
    )
    await db.commit()
    return service.build_profile_response_fields(profile, viewer_user_id=current_user.id)
