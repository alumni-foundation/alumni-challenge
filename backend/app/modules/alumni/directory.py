import re
import uuid
from dataclasses import dataclass

from sqlalchemy import bindparam, exists, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alumni.models import (
    AlumniProfile,
    AlumniSkill,
    ProfileVisibility,
    Skill,
    VerificationStatus,
)
from app.modules.identity.models import User, UserStatus

# Letters and digits only. Dropping everything else (including underscores and every
# tsquery operator character) is what makes it impossible to inject query syntax.
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MAX_TERMS = 8
_MAX_TERM_LENGTH = 50

# The directory is for signed-in members and only ever lists these two. Connections-only
# and private profiles never appear in a general scan, whoever is looking, so search can
# never be used to find them.
_LISTABLE = (ProfileVisibility.PUBLIC, ProfileVisibility.MEMBERS_ONLY)

# Counting every match gets slower as the table grows, so the total stops at this number.
# The X-Total-Count header therefore means "this many, or more" once it reaches the cap.
TOTAL_COUNT_CAP = 10_000


@dataclass(frozen=True)
class DirectoryPage:
    profiles: list[AlumniProfile]
    total: int


def build_prefix_query(raw: str) -> str | None:
    """
    Turns what the user typed into a safe tsquery string: every word becomes a prefix match
    and all words must match ("jo eng" finds John, Engineer). Returns None when the text has
    no searchable words at all.
    """
    words = [w[:_MAX_TERM_LENGTH] for w in _WORD_RE.findall(raw.lower())[:_MAX_TERMS]]
    if not words:
        return None
    return " & ".join(f"{w}:*" for w in words)


async def search_directory(
    db: AsyncSession,
    *,
    q: str | None,
    school_id: uuid.UUID | None,
    country: str | None,
    graduation_year: int | None,
    verified: bool | None,
    skill: str | None,
    limit: int,
    offset: int,
) -> DirectoryPage:
    conditions = [
        # Written into the SQL as literals (not bind parameters) so Postgres can see that the
        # filter matches the partial index behind the plain listing.
        AlumniProfile.profile_visibility.in_(
            bindparam("listable", list(_LISTABLE), expanding=True, literal_execute=True)
        ),
        # Suspended and deleted accounts must not be discoverable.
        User.status == UserStatus.ACTIVE,
    ]
    if school_id is not None:
        conditions.append(AlumniProfile.school_id == school_id)
    if country:
        conditions.append(func.lower(AlumniProfile.country) == country.strip().lower())
    if graduation_year is not None:
        conditions.append(AlumniProfile.graduation_year == graduation_year)
    if verified:
        conditions.append(AlumniProfile.verification_status == VerificationStatus.VERIFIED)
    if skill:
        conditions.append(
            exists().where(
                AlumniSkill.alumni_profile_id == AlumniProfile.id,
                AlumniSkill.skill_id == Skill.id,
                func.lower(Skill.name) == skill.strip().lower(),
            )
        )

    rank = None
    if q is not None and q.strip():
        tsquery_text = build_prefix_query(q)
        if tsquery_text is None:
            # They typed something, but nothing in it is searchable ("!!!"): no results,
            # not "everything".
            return DirectoryPage(profiles=[], total=0)
        tsquery = func.to_tsquery(literal_column("'simple'"), tsquery_text)
        conditions.append(AlumniProfile.search_vector.op("@@")(tsquery))
        rank = func.ts_rank_cd(AlumniProfile.search_vector, tsquery)

    matching = (
        select(AlumniProfile.id)
        .join(User, User.id == AlumniProfile.user_id)
        .where(*conditions)
        .limit(TOTAL_COUNT_CAP)
        .subquery()
    )
    total = await db.scalar(select(func.count()).select_from(matching))

    stmt = select(AlumniProfile).join(User, User.id == AlumniProfile.user_id).where(*conditions)
    if rank is not None:
        stmt = stmt.order_by(rank.desc(), AlumniProfile.created_at.desc(), AlumniProfile.id)
    else:
        stmt = stmt.order_by(AlumniProfile.created_at.desc(), AlumniProfile.id)
    stmt = stmt.limit(limit).offset(offset)

    profiles = list((await db.scalars(stmt)).all())
    return DirectoryPage(profiles=profiles, total=total or 0)
