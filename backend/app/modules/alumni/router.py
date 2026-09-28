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
        user=current_user,
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
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.patch("/profile", response_model=schemas.AlumniProfileResponse)
async def update_profile(
    body: schemas.AlumniProfileUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    updates = body.model_dump(exclude_unset=True)
    profile = await service.update_own_profile(db, user=current_user, **updates)
    await db.commit()
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.get("/profile/me", response_model=schemas.AlumniProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.get_own_profile(db, user_id=current_user.id)
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.put("/profile/skills", response_model=schemas.AlumniProfileResponse)
async def set_my_skills(
    body: schemas.SetTagsRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.set_skills(db, user_id=current_user.id, names=body.names)
    await db.commit()
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.put("/profile/interests", response_model=schemas.AlumniProfileResponse)
async def set_my_interests(
    body: schemas.SetTagsRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.set_interests(db, user_id=current_user.id, names=body.names)
    await db.commit()
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.get("/directory", response_model=list[schemas.AlumniProfileSummary])
async def list_directory(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AlumniProfile]:
    """
    Authenticated members only. Only profiles set to public or members_only
    are listed: connections_only and private profiles never appear in a
    general scan, whoever is looking. Summary fields only.
    """
    stmt = (
        select(AlumniProfile)
        .where(AlumniProfile.profile_visibility.in_(["public", "members_only"]))
        .order_by(AlumniProfile.created_at.desc(), AlumniProfile.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await db.scalars(stmt)).all())


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
    return await service.build_profile_response(db, profile=profile, viewer_user_id=viewer_id)


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
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)


@router.post("/{profile_id}/vouch", response_model=schemas.AlumniProfileResponse)
async def vouch(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    profile = await service.vouch_for_profile(
        db, profile_id=profile_id, voucher_user_id=current_user.id
    )
    await db.commit()
    return await service.build_profile_response(db, profile=profile, viewer_user_id=current_user.id)
