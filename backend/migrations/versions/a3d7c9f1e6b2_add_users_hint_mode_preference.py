"""add users.hint_mode_preference

Revision ID: a3d7c9f1e6b2
Revises: f2c8a1e6d4b9
Create Date: 2026-08-23 11:00:00.000000

Persists a logged-in user's hint-mode toggle so it carries over between
puzzles/sessions instead of always resetting to off -- see
GuessPanel.jsx's initial hintMode state and PATCH /api/auth/hint-mode.
Anonymous play has nowhere to persist this (no user row), so it keeps
defaulting to off there, same as before.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3d7c9f1e6b2'
down_revision = 'f2c8a1e6d4b9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hint_mode_preference', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('hint_mode_preference')
