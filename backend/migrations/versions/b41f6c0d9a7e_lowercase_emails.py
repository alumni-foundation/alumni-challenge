"""emails are stored in lower case

Revision ID: b41f6c0d9a7e
Revises: 706e39cafbf4
Create Date: 2026-10-24 09:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


revision: str = 'b41f6c0d9a7e'
down_revision: str | None = '706e39cafbf4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Two accounts that differ only in case would make this fail on purpose: someone has to
    # decide which one is real. The unique index on email then rejects the second UPDATE.
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")
    op.create_check_constraint("ck_users_email_lowercase", "users", "email = lower(email)")


def downgrade() -> None:
    # The original letter case is not recoverable and was never meaningful.
    op.drop_constraint("ck_users_email_lowercase", "users", type_="check")
