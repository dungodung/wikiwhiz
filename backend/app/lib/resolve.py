"""Resolve free-text guesses to a real Wikipedia article.

Users type whatever they think the answer is, not necessarily an exact title.
Resolution order: normalized-guess cache -> exact title lookup (follows
redirects) -> full-text search fallback -> re-resolve the top search hit.
Results are cached in title_resolutions (a global cache, independent of which
answer article is being played, since "Einstein" always resolves the same way).
"""

import logging
from datetime import datetime, timezone

import requests

from ..extensions import db
from ..models.title_resolution import TitleResolution
from .mediawiki_api import MediaWikiClient
from .similarity import normalize_text

logger = logging.getLogger(__name__)


def resolve_guess_text(client: MediaWikiClient, guess_text: str) -> dict | None:
    normalized = normalize_text(guess_text)
    if not normalized:
        return None

    cached = db.session.get(TitleResolution, normalized)
    if cached is not None:
        if cached.resolved_pageid is None:
            return None
        return {"pageid": cached.resolved_pageid, "title": cached.resolved_title}

    try:
        result = client.resolve_title(guess_text) or client.search_title(guess_text)
    except requests.RequestException:
        # Transient failure (rate limit, network blip): don't cache a false
        # negative, just leave this guess unresolved for this one request.
        logger.warning("Title resolution failed for guess_text=%r", guess_text, exc_info=True)
        return None

    row = TitleResolution(
        normalized_guess=normalized,
        resolved_pageid=result["pageid"] if result else None,
        resolved_title=result["title"] if result else None,
        updated_at=datetime.now(timezone.utc),
    )
    db.session.merge(row)
    db.session.commit()

    return result
