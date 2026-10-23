"""alumni directory full text search

Revision ID: 23580883c3ec
Revises: a7582de1c2f4
Create Date: 2026-10-11 06:44:57.161432

The search document is rebuilt by database triggers, not by application code, so no code
path (a future bulk import, a script, a manual fix) can leave it stale.

Weights: A name, B profession + company, C country + skills + interests, D bio.
The 'simple' text config is used on purpose: no stemming and no stop words, so names such as
"James" or "Wanjiku" are indexed exactly as written. The API matches word prefixes instead.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "23580883c3ec"
down_revision: str | None = "a7582de1c2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BUILD_FN = """
CREATE OR REPLACE FUNCTION alumni_profile_search_vector(
    p_id uuid, p_full_name text, p_profession text, p_company text, p_country text, p_bio text
) RETURNS tsvector AS $$
    SELECT
        setweight(to_tsvector('simple', coalesce(p_full_name, '')), 'A')
        || setweight(
            to_tsvector('simple', coalesce(p_profession, '') || ' ' || coalesce(p_company, '')),
            'B')
        || setweight(
            to_tsvector(
                'simple',
                coalesce(p_country, '')
                || ' ' || coalesce((
                    SELECT string_agg(s.name, ' ')
                    FROM alumni_skills a JOIN skills s ON s.id = a.skill_id
                    WHERE a.alumni_profile_id = p_id), '')
                || ' ' || coalesce((
                    SELECT string_agg(i.name, ' ')
                    FROM alumni_interests ai JOIN interests i ON i.id = ai.interest_id
                    WHERE ai.alumni_profile_id = p_id), '')
            ),
            'C')
        || setweight(to_tsvector('simple', coalesce(p_bio, '')), 'D')
$$ LANGUAGE sql STABLE;
"""

_PROFILE_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION alumni_profiles_search_vector_trg() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := alumni_profile_search_vector(
        NEW.id, NEW.full_name, NEW.profession, NEW.company, NEW.country, NEW.bio
    );
    RETURN NEW;
END
$$ LANGUAGE plpgsql;
"""

# Fires on skill / interest links being added or removed and refreshes the owning profile.
_LINK_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION alumni_links_search_vector_trg() RETURNS trigger AS $$
DECLARE
    pid uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        pid := OLD.alumni_profile_id;
    ELSE
        pid := NEW.alumni_profile_id;
    END IF;
    UPDATE alumni_profiles p
    SET search_vector = alumni_profile_search_vector(
        p.id, p.full_name, p.profession, p.company, p.country, p.bio
    )
    WHERE p.id = pid;
    RETURN NULL;
END
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.add_column(
        "alumni_profiles", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True)
    )
    op.create_index(
        "ix_alumni_profiles_search_vector",
        "alumni_profiles",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_index(
        "ix_alumni_profiles_directory_listing",
        "alumni_profiles",
        [sa.text("created_at DESC"), "id"],
        unique=False,
        postgresql_where=sa.text("profile_visibility IN ('public', 'members_only')"),
    )

    op.execute(_BUILD_FN)
    op.execute(_PROFILE_TRIGGER_FN)
    op.execute(_LINK_TRIGGER_FN)

    # UPDATE OF <columns> means a write that only touches search_vector (the link trigger
    # does this) does not re-fire the profile trigger, so there is no recursion.
    op.execute(
        """
        CREATE TRIGGER trg_alumni_profiles_search_vector
        BEFORE INSERT OR UPDATE OF full_name, profession, company, country, bio
        ON alumni_profiles
        FOR EACH ROW EXECUTE FUNCTION alumni_profiles_search_vector_trg()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_alumni_skills_search_vector
        AFTER INSERT OR DELETE ON alumni_skills
        FOR EACH ROW EXECUTE FUNCTION alumni_links_search_vector_trg()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_alumni_interests_search_vector
        AFTER INSERT OR DELETE ON alumni_interests
        FOR EACH ROW EXECUTE FUNCTION alumni_links_search_vector_trg()
        """
    )

    # Backfill profiles that already exist.
    op.execute(
        """
        UPDATE alumni_profiles
        SET search_vector = alumni_profile_search_vector(
            id, full_name, profession, company, country, bio
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_alumni_interests_search_vector ON alumni_interests")
    op.execute("DROP TRIGGER IF EXISTS trg_alumni_skills_search_vector ON alumni_skills")
    op.execute("DROP TRIGGER IF EXISTS trg_alumni_profiles_search_vector ON alumni_profiles")
    op.execute("DROP FUNCTION IF EXISTS alumni_links_search_vector_trg()")
    op.execute("DROP FUNCTION IF EXISTS alumni_profiles_search_vector_trg()")
    op.execute(
        "DROP FUNCTION IF EXISTS alumni_profile_search_vector(uuid, text, text, text, text, text)"
    )
    op.drop_index(
        "ix_alumni_profiles_directory_listing",
        table_name="alumni_profiles",
        postgresql_where=sa.text("profile_visibility IN ('public', 'members_only')"),
    )
    op.drop_index(
        "ix_alumni_profiles_search_vector", table_name="alumni_profiles", postgresql_using="gin"
    )
    op.drop_column("alumni_profiles", "search_vector")
