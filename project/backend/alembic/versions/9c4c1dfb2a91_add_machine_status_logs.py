"""add machine status logs

Revision ID: 9c4c1dfb2a91
Revises: 34bcd027b891
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa

revision = '9c4c1dfb2a91'
down_revision = '34bcd027b891'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'machine_status_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('machine_id', sa.Integer(), nullable=False),
        sa.Column('previous_status', sa.String(length=32), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('is_running', sa.Boolean(), nullable=True),
        sa.Column('changed', sa.Boolean(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_machine_status_logs_id'), 'machine_status_logs', ['id'], unique=False)
    op.create_index(op.f('ix_machine_status_logs_machine_id'), 'machine_status_logs', ['machine_id'], unique=False)
    op.create_index(op.f('ix_machine_status_logs_recorded_at'), 'machine_status_logs', ['recorded_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_machine_status_logs_recorded_at'), table_name='machine_status_logs')
    op.drop_index(op.f('ix_machine_status_logs_machine_id'), table_name='machine_status_logs')
    op.drop_index(op.f('ix_machine_status_logs_id'), table_name='machine_status_logs')
    op.drop_table('machine_status_logs')