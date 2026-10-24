"""
Checking a booking's answers against the event's question definitions. Questions are data, so
the same code serves a golf day and a networking dinner.
"""

import math
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ValidationError
from app.modules.bookings.schemas import AnswerInput
from app.modules.events.models import EventQuestion, QuestionAskedOf, QuestionKind
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType

MAX_TEXT = 500
MAX_LONG_TEXT = 5000


@dataclass(frozen=True)
class CleanAnswer:
    question_id: uuid.UUID
    position: int
    value: Any


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == []


def _bad(question: EventQuestion, message: str) -> ValidationError:
    return ValidationError(f"{question.label}: {message}", code="invalid_answer")


async def _check_value(db: AsyncSession, question: EventQuestion, value: Any) -> Any:
    kind = question.kind
    if kind in (QuestionKind.TEXT, QuestionKind.LONG_TEXT):
        if not isinstance(value, str):
            raise _bad(question, "enter text.")
        limit = MAX_TEXT if kind == QuestionKind.TEXT else MAX_LONG_TEXT
        cleaned = value.strip()
        if len(cleaned) > limit:
            raise _bad(question, f"keep it under {limit} characters.")
        return cleaned
    if kind == QuestionKind.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise _bad(question, "enter a number.")
        if isinstance(value, float) and not math.isfinite(value):
            raise _bad(question, "enter a number.")
        return value
    if kind == QuestionKind.BOOLEAN:
        if not isinstance(value, bool):
            raise _bad(question, "answer yes or no.")
        return value
    allowed = {o["value"] for o in (question.options or [])}
    if kind == QuestionKind.CHOICE:
        if not isinstance(value, str) or value not in allowed:
            raise _bad(question, "choose one of the listed options.")
        return value
    if kind == QuestionKind.MULTI_CHOICE:
        if (
            not isinstance(value, list)
            or not all(isinstance(v, str) and v in allowed for v in value)
            or len(set(value)) != len(value)
        ):
            raise _bad(question, "choose from the listed options.")
        return value
    if kind == QuestionKind.SCHOOL:
        try:
            school_id = uuid.UUID(str(value))
        except ValueError:
            raise _bad(question, "choose a school.") from None
        school = await db.get(Organization, school_id)
        if (
            school is None
            or school.type != OrganizationType.SCHOOL
            or school.status != OrganizationStatus.ACTIVE
        ):
            raise _bad(question, "choose a school.")
        return str(school_id)
    raise _bad(question, "unsupported question.")  # pragma: no cover


async def validate_answers(
    db: AsyncSession,
    *,
    event_id: uuid.UUID,
    party_size: int,
    answers: list[AnswerInput],
) -> list[CleanAnswer]:
    questions = list(
        (await db.scalars(select(EventQuestion).where(EventQuestion.event_id == event_id))).all()
    )
    by_key = {q.key: q for q in questions}

    given: dict[tuple[str, int], Any] = {}
    for a in answers:
        question = by_key.get(a.question_key)
        if question is None:
            raise ValidationError(
                f"There is no question called {a.question_key}.", code="unknown_question"
            )
        if a.position > party_size:
            raise ValidationError(
                "An answer is for a person who is not in the booking.", code="invalid_answer"
            )
        if question.asked_of == QuestionAskedOf.BOOKER and a.position != 1:
            raise _bad(question, "this question is only asked of the booker.")
        key = (a.question_key, a.position)
        if key in given:
            raise _bad(question, "answered twice.")
        given[key] = a.value

    clean: list[CleanAnswer] = []
    for question in questions:
        positions = (
            [1] if question.asked_of == QuestionAskedOf.BOOKER else list(range(1, party_size + 1))
        )
        for position in positions:
            value = given.get((question.key, position))
            if _is_blank(value):
                if question.required:
                    who = "" if len(positions) == 1 else f" (person {position})"
                    raise ValidationError(
                        f"{question.label}{who}: this answer is needed.", code="answer_required"
                    )
                continue
            clean.append(
                CleanAnswer(question.id, position, await _check_value(db, question, value))
            )
    return clean
