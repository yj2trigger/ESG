"""add timezone to datetime columns

Revision ID: 34bcd027b891
Revises:
Create Date: 2026-05-25

"""
from alembic import op
import sqlalchemy as sa

revision = '34bcd027b891'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'machines', 'reserved_until',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        'email_verifications', 'expires_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'machines', 'reserved_until',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        'email_verifications', 'expires_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
