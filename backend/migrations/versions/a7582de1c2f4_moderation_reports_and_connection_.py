"""moderation reports and connection blocked_by

Revision ID: a7582de1c2f4
Revises: 3c681dec8dd8
Create Date: 2026-10-10 09:17:26.239651

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a7582de1c2f4'
down_revision: str | None = '3c681dec8dd8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('reports',
    sa.Column('reporter_user_id', sa.UUID(), nullable=False),
    sa.Column('target_type', sa.Enum('profile', 'message', 'content', name='report_target_type'), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('open', 'reviewing', 'resolved', 'dismissed', name='report_status'), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['reporter_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_target_id'), 'reports', ['target_id'], unique=False)
    op.create_index(op.f('ix_reports_target_type'), 'reports', ['target_type'], unique=False)
    op.add_column('connections', sa.Column('blocked_by', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_connections_blocked_by_users', 'connections', 'users', ['blocked_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_connections_blocked_by_users', 'connections', type_='foreignkey')
    op.drop_column('connections', 'blocked_by')
    op.drop_index(op.f('ix_reports_target_type'), table_name='reports')
    op.drop_index(op.f('ix_reports_target_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_table('reports')
    # Alembic does not drop Postgres ENUM types when it drops the table that used them.
    sa.Enum(name='report_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='report_target_type').drop(op.get_bind(), checkfirst=True)
