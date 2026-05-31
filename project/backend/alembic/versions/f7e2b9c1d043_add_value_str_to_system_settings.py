"""add value_str to system_settings

Revision ID: f7e2b9c1d043
Revises: 9c4c1dfb2a91
Create Date: 2026-05-31

"""
from alembic import op
import sqlalchemy as sa

revision = 'f7e2b9c1d043'
down_revision = '9c4c1dfb2a91'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('system_settings', sa.Column('value_str', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('system_settings', 'value_str')
