"""add edit_count and distinct_editor_count clue types

Revision ID: d1a9f4e7b2c3
Revises: c8e2a1f4d6b9
Create Date: 2026-08-20 19:30:00.000000

Both are sourced from the Wiki Replica (revision table), which can give an
exact count in one query where the paginated Action API (capped at 500/5000
per call) would need dozens of round-trips for a heavily-edited article --
see .claude/skills/wikiwhiz-content-author/references/candidate_criteria.md.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'd1a9f4e7b2c3'
down_revision = 'c8e2a1f4d6b9'
branch_labels = None
depends_on = None

_OLD_TYPES = (
    "commons_image", "dyk_or_notable_fact", "wikidata_fact", "infobox_fact",
    "categories", "etymology", "wikisource_excerpt", "wikivoyage_fact",
    "pageviews", "top_citation", "incoming_links", "long_section_title",
    "creation_year", "langlinks_count",
)
_NEW_TYPES = _OLD_TYPES + ("edit_count", "distinct_editor_count")


def upgrade():
    op.execute(
        "ALTER TABLE clues MODIFY COLUMN clue_type ENUM("
        + ", ".join(f"'{t}'" for t in _NEW_TYPES)
        + ") NOT NULL"
    )


def downgrade():
    op.execute(
        "ALTER TABLE clues MODIFY COLUMN clue_type ENUM("
        + ", ".join(f"'{t}'" for t in _OLD_TYPES)
        + ") NOT NULL"
    )
