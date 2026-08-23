"""add guess_attempts.is_pass

Revision ID: f2c8a1e6d4b9
Revises: e5f8b3a9d1c7
Create Date: 2026-08-23 10:00:00.000000

A pass burns an attempt (advances clues_revealed/guesses_made exactly like
a wrong guess) without submitting any guess text at all -- see
game/service.py::process_pass. is_pass distinguishes these rows from real
guesses so the frontend can show "Passed" instead of a resolved-title link.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c8a1e6d4b9'
down_revision = 'e5f8b3a9d1c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('guess_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_pass', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('guess_attempts', schema=None) as batch_op:
        batch_op.drop_column('is_pass')
