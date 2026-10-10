"""Shared title-leak guard, used by both scripts/db_add_clue.py and the admin
API (backend/app/blueprints/admin/routes.py) so clue insertion/editing goes
through identical validation no matter which path calls it.
"""

import re

from ..models.article import Article
from ..models.clue import Clue

MIN_CLUES_FOR_READY = 5

# "This Wikipedia article was created in 2003" says next to nothing about the
# subject -- nearly every established article dates from 2001-2010 -- so it's
# only allowed for genuinely recent articles, where the year actually hints
# at something (the subject is new, or newly notable).
MIN_CREATION_YEAR_FOR_CLUE = 2020
_CREATED_IN_RE = re.compile(r"\bwas created in\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(1\d{3}|20\d{2})\b")


def leaks_title(clue_text: str, article: Article) -> bool:
    haystack = clue_text.casefold()
    for candidate in (article.wiki_title, article.display_title):
        if candidate and candidate.casefold() in haystack:
            return True
    return False


def is_stale_creation_year(clue_type: str, clue_text: str) -> bool:
    """True for an article-creation-year clue about a pre-2020 article.

    Applies to the creation_year type, and to any other type whose text
    reads "...was created in <year>", so the rule can't be sidestepped by
    filing the same sentence under a different type. A creation-year clue
    with no recognizable year counts as stale too -- there's nothing to
    show it's recent.
    """
    if clue_type != "creation_year" and not _CREATED_IN_RE.search(clue_text):
        return False
    years = [int(y) for y in _YEAR_RE.findall(clue_text)]
    return not years or max(years) < MIN_CREATION_YEAR_FOR_CLUE


def usable_clue_count(session, article_id: int) -> int:
    return session.query(Clue).filter_by(article_id=article_id, is_title_leaking=False).count()


def can_promote_to_ready(session, article: Article) -> tuple[bool, int]:
    count = usable_clue_count(session, article.id)
    return count >= MIN_CLUES_FOR_READY, count
