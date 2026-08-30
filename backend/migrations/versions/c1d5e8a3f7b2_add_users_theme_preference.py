"""add users.theme_preference

Revision ID: c1d5e8a3f7b2
Revises: b4e6d29a7f31
Create Date: 2026-08-29 09:00:00.000000

Persists a logged-in user's light/dark theme choice so it carries over
between sessions -- see PATCH /api/auth/theme. Anonymous play persists the
same choice in localStorage instead (no user row to attach it to).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d5e8a3f7b2'
down_revision = 'b4e6d29a7f31'
branch_labels = None
depends_on = None

_theme_enum = sa.Enum('dark', 'light', name='theme_preference')


def upgrade():
    _theme_enum.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('theme_preference', _theme_enum, server_default='dark', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('theme_preference')
    _theme_enum.drop(op.get_bind(), checkfirst=True)
