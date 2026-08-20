"""tile-based guessing: link_cache_nodes.node_tiles, drop title_resolutions

Revision ID: f3a1c9d02b7e
Revises: a74fc6ad92ee
Create Date: 2026-08-19 19:10:00.000000

Guesses are now filled in directly on the article's fixed-length tile board
(see backend/app/lib/slot_pattern.py) instead of resolved from free text, so
title_resolutions (the old free-text-guess cache) is no longer used anywhere
and is dropped. link_cache_nodes gains node_tiles, the normalized tile string
each cached same-shape neighbor spells out -- this is now looked up directly
by (answer_article_id, node_tiles) to resolve a guess and its precomputed
degree in one indexed query, with no live API call at guess time. Existing
link_cache_nodes rows predate the same-shape filter and node_tiles entirely,
so they're cleared here -- scripts/precompute_link_cache.py needs to be
re-run per article regardless.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a1c9d02b7e'
down_revision = 'a74fc6ad92ee'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM link_cache_nodes")

    with op.batch_alter_table('link_cache_nodes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('node_tiles', sa.String(length=255), nullable=False))
        batch_op.create_index('ix_link_cache_answer_tiles', ['answer_article_id', 'node_tiles'], unique=False)

    op.drop_table('title_resolutions')


def downgrade():
    op.create_table(
        'title_resolutions',
        sa.Column('normalized_guess', sa.String(length=255), nullable=False),
        sa.Column('resolved_pageid', sa.Integer(), nullable=True),
        sa.Column('resolved_title', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('normalized_guess'),
    )

    with op.batch_alter_table('link_cache_nodes', schema=None) as batch_op:
        batch_op.drop_index('ix_link_cache_answer_tiles')
        batch_op.drop_column('node_tiles')
