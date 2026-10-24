"""outbox_dedupe_key

Revision ID: f4a9d1c6b805
Revises: e8b3c5d70f42
Create Date: 2026-10-24 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f4a9d1c6b805'
down_revision: str | None = 'e8b3c5d70f42'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('domain_events', sa.Column('dedupe_key', sa.String(length=200), nullable=True))
    op.create_index(
        'uq_domain_events_dedupe_key',
        'domain_events',
        ['dedupe_key'],
        unique=True,
        postgresql_where=sa.text('dedupe_key IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index(
        'uq_domain_events_dedupe_key',
        table_name='domain_events',
        postgresql_where=sa.text('dedupe_key IS NOT NULL'),
    )
    op.drop_column('domain_events', 'dedupe_key')
