"""add guess_attempts.degrees_pending

Revision ID: c8e2a1f4d6b9
Revises: f3a1c9d02b7e
Create Date: 2026-08-19 21:05:00.000000

The live BFS fallback (lib/degrees.py::compute_degrees_live) can take a
while for two hub-like articles -- rather than block the guess response on
it, the guess is now accepted/rejected immediately and degrees_pending marks
an attempt whose degrees value is still being computed in a background
thread (see game/service.py). The frontend polls until it flips to False.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e2a1f4d6b9'
down_revision = 'f3a1c9d02b7e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('guess_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('degrees_pending', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('guess_attempts', schema=None) as batch_op:
        batch_op.drop_column('degrees_pending')
