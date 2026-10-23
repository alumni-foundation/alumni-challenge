"""file purpose, organization, dimensions

Revision ID: 740d3da6b74d
Revises: 23580883c3ec
Create Date: 2026-10-23 20:13:22.905330

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '740d3da6b74d'
down_revision: str | None = '23580883c3ec'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PURPOSE_VALUES = ('avatar', 'organization_logo', 'event_poster')


def upgrade() -> None:
    purpose = postgresql.ENUM(*_PURPOSE_VALUES, name='file_purpose', create_type=False)
    purpose.create(op.get_bind(), checkfirst=True)

    # No upload code existed before this migration, so the only rows that can exist are
    # organization logos pointed at by hand. The temporary defaults let the NOT NULL columns
    # be added to a table that already has rows, and are dropped straight after.
    op.add_column(
        'files',
        sa.Column('purpose', purpose, nullable=False, server_default='organization_logo'),
    )
    op.add_column('files', sa.Column('width', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('files', sa.Column('height', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('files', 'purpose', server_default=None)
    op.alter_column('files', 'width', server_default=None)
    op.alter_column('files', 'height', server_default=None)

    op.add_column('files', sa.Column('organization_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_files_owner_user_id'), 'files', ['owner_user_id'], unique=False)
    op.create_foreign_key(
        'fk_files_organization_id',
        'files',
        'organizations',
        ['organization_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_files_organization_id', 'files', type_='foreignkey')
    op.drop_index(op.f('ix_files_owner_user_id'), table_name='files')
    op.drop_column('files', 'organization_id')
    op.drop_column('files', 'height')
    op.drop_column('files', 'width')
    op.drop_column('files', 'purpose')
    postgresql.ENUM(name='file_purpose').drop(op.get_bind(), checkfirst=True)
