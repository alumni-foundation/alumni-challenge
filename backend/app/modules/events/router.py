import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db_session
from app.infrastructure.storage import Storage, get_storage
from app.modules.bookings import service as bookings_service
from app.modules.events import access, schemas, service
from app.modules.events.models import Event, EventCategory
from app.modules.files import attach
from app.modules.identity.dependencies import get_current_user, get_current_user_optional
from app.modules.identity.models import User

router = APIRouter(prefix="/events", tags=["events"])
series_router = APIRouter(prefix="/event-series", tags=["events"])


async def _detail(db: AsyncSession, event: Event, user: User | None) -> schemas.EventDetail:
    roles = await access.event_roles(db, user=user, organization_id=event.organization_id)
    detail = await service.build_detail(db, event, can_manage=bool(roles & access.MANAGER_ROLES))
    detail.my_booking = await bookings_service.my_booking_brief(db, event_id=event.id, user=user)
    return detail


# --------------------------------------------------------------------------- discovery


@router.get("", response_model=list[schemas.EventSummary])
async def list_events(
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_current_user_optional),
    category: EventCategory | None = None,
    organization_id: uuid.UUID | None = None,
    series_id: uuid.UUID | None = None,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    q: str | None = Query(default=None, max_length=100),
    past: bool = Query(default=False, description="Events that have already ended"),
    manage: bool = Query(
        default=False,
        description="The events you run, drafts and cancelled ones included. Needs sign-in.",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[schemas.EventSummary]:
    """
    Upcoming published events you are allowed to see, soonest first. Signed-out visitors see
    public events only. The total is in the X-Total-Count header.
    """
    events, total = await service.list_events(
        db,
        viewer=viewer,
        category=category.value if category else None,
        organization_id=organization_id,
        series_id=series_id,
        starts_after=starts_after,
        starts_before=starts_before,
        q=q,
        past=past,
        manage=manage,
        limit=limit,
        offset=offset,
    )
    response.headers["X-Total-Count"] = str(total)
    return await service.build_summaries(db, events)


@router.get("/{event_id}", response_model=schemas.EventDetail)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_current_user_optional),
) -> schemas.EventDetail:
    event, _roles = await access.get_event_for_viewer(db, event_id=event_id, viewer=viewer)
    return await _detail(db, event, viewer)


# ---------------------------------------------------------------------------- organize


@router.post("", response_model=schemas.EventDetail, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: schemas.EventCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    """Creates a draft. With no `slots`, one slot covering the whole event is made."""
    event = await service.create_event(db, actor=user, body=body)
    await db.commit()
    return await _detail(db, event, user)


@router.patch("/{event_id}", response_model=schemas.EventDetail)
async def update_event(
    event_id: uuid.UUID,
    body: schemas.EventUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.update_event(db, actor=user, event=event, body=body)
    await db.commit()
    return await _detail(db, event, user)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Only a draft can be deleted."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user, admin_only=True)
    await service.delete_draft(db, actor=user, event=event)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{event_id}/publish", response_model=schemas.EventDetail)
async def publish_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user, admin_only=True)
    await service.publish(db, actor=user, event=event)
    await db.commit()
    return await _detail(db, event, user)


@router.post("/{event_id}/close", response_model=schemas.EventDetail)
async def close_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    """Stop taking bookings. Existing bookings are untouched."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.close_registration(db, actor=user, event=event)
    await db.commit()
    return await _detail(db, event, user)


@router.post("/{event_id}/reopen", response_model=schemas.EventDetail)
async def reopen_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.reopen_registration(db, actor=user, event=event)
    await db.commit()
    return await _detail(db, event, user)


@router.post("/{event_id}/complete", response_model=schemas.EventDetail)
async def complete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.complete(db, actor=user, event=event)
    await db.commit()
    return await _detail(db, event, user)


@router.post("/{event_id}/cancel", response_model=schemas.EventDetail)
async def cancel_event(
    event_id: uuid.UUID,
    body: schemas.CancelEventRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user, admin_only=True)
    await service.cancel(db, actor=user, event=event, reason=body.reason)
    await db.commit()
    return await _detail(db, event, user)


# ------------------------------------------------------------------------------ poster


@router.put("/{event_id}/poster", response_model=schemas.EventDetail)
async def set_poster(
    event_id: uuid.UUID,
    body: schemas.SetPosterRequest,
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    """Use an uploaded picture (purpose `event_poster`, uploaded for this organizer)."""
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    old_key = await attach.set_event_poster(db, event=event, file_id=body.file_id)
    await db.commit()
    if old_key:
        await storage.delete(old_key)
    return await _detail(db, event, user)


@router.delete("/{event_id}/poster", response_model=schemas.EventDetail)
async def remove_poster(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    storage: Storage = Depends(get_storage),
    user: User = Depends(get_current_user),
) -> schemas.EventDetail:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    old_key = await attach.clear_event_poster(db, event=event)
    await db.commit()
    if old_key:
        await storage.delete(old_key)
    return await _detail(db, event, user)


# ------------------------------------------------------------------------------- slots


@router.post(
    "/{event_id}/slots", response_model=schemas.SlotOut, status_code=status.HTTP_201_CREATED
)
async def add_slot(
    event_id: uuid.UUID,
    body: schemas.SlotInput,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.SlotOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    slot = await service.add_slot(db, actor=user, event=event, body=body)
    await db.commit()
    return service.slot_out(slot)


@router.patch("/{event_id}/slots/{slot_id}", response_model=schemas.SlotOut)
async def update_slot(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    body: schemas.SlotUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.SlotOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    slot = await service.update_slot(db, actor=user, event=event, slot_id=slot_id, body=body)
    await db.commit()
    return service.slot_out(slot)


@router.delete("/{event_id}/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slot(
    event_id: uuid.UUID,
    slot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.delete_slot(db, actor=user, event=event, slot_id=slot_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- questions


@router.post(
    "/{event_id}/questions",
    response_model=schemas.QuestionOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    event_id: uuid.UUID,
    body: schemas.QuestionCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.QuestionOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    question = await service.add_question(db, actor=user, event=event, body=body)
    await db.commit()
    return schemas.QuestionOut.model_validate(question)


@router.patch("/{event_id}/questions/{question_id}", response_model=schemas.QuestionOut)
async def update_question(
    event_id: uuid.UUID,
    question_id: uuid.UUID,
    body: schemas.QuestionUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.QuestionOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    question = await service.update_question(
        db, actor=user, event=event, question_id=question_id, body=body
    )
    await db.commit()
    return schemas.QuestionOut.model_validate(question)


@router.delete("/{event_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    event_id: uuid.UUID,
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.delete_question(db, actor=user, event=event, question_id=question_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- consents


@router.post(
    "/{event_id}/consents",
    response_model=schemas.ConsentOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_consent(
    event_id: uuid.UUID,
    body: schemas.ConsentCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.ConsentOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    consent = await service.add_consent(db, actor=user, event=event, body=body)
    await db.commit()
    return schemas.ConsentOut.model_validate(consent)


@router.patch("/{event_id}/consents/{consent_id}", response_model=schemas.ConsentOut)
async def update_consent(
    event_id: uuid.UUID,
    consent_id: uuid.UUID,
    body: schemas.ConsentUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.ConsentOut:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    consent = await service.update_consent(
        db, actor=user, event=event, consent_id=consent_id, body=body
    )
    await db.commit()
    return schemas.ConsentOut.model_validate(consent)


@router.delete("/{event_id}/consents/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_consent(
    event_id: uuid.UUID,
    consent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    event = await access.get_event_for_manager(db, event_id=event_id, user=user)
    await service.delete_consent(db, actor=user, event=event, consent_id=consent_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------------------- series


@series_router.post("", response_model=schemas.SeriesOut, status_code=status.HTTP_201_CREATED)
async def create_series(
    body: schemas.SeriesCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> schemas.SeriesOut:
    series = await service.create_series(db, actor=user, body=body)
    await db.commit()
    return schemas.SeriesOut(
        id=series.id,
        organization_id=series.organization_id,
        title=series.title,
        description=series.description,
    )


@series_router.get("", response_model=list[schemas.SeriesOut])
async def my_series(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> list[schemas.SeriesOut]:
    """The series of the organizations you run events for (to pick one when making a round)."""
    return [
        schemas.SeriesOut(
            id=s.id, organization_id=s.organization_id, title=s.title, description=s.description
        )
        for s in await service.list_my_series(db, user=user)
    ]


@series_router.get("/{series_id}", response_model=schemas.SeriesDetail)
async def get_series(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    viewer: User | None = Depends(get_current_user_optional),
) -> schemas.SeriesDetail:
    return await service.series_detail(db, series_id=series_id, viewer=viewer)
