"""Shared title-leak guard, used by both scripts/db_add_clue.py and the admin
API (backend/app/blueprints/admin/routes.py) so clue insertion/editing goes
through identical validation no matter which path calls it.
"""

from ..models.article import Article
from ..models.clue import Clue

MIN_CLUES_FOR_READY = 5


def leaks_title(clue_text: str, article: Article) -> bool:
    haystack = clue_text.casefold()
    for candidate in (article.wiki_title, article.display_title):
        if candidate and candidate.casefold() in haystack:
            return True
    return False


def usable_clue_count(session, article_id: int) -> int:
    return session.query(Clue).filter_by(article_id=article_id, is_title_leaking=False).count()


def can_promote_to_ready(session, article: Article) -> tuple[bool, int]:
    count = usable_clue_count(session, article.id)
    return count >= MIN_CLUES_FOR_READY, count
