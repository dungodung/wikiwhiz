"""Hint-mode autocomplete: turn a partially-filled letter pattern into real
Wikipedia title suggestions.

The player can fill in any subset of letter boxes, in any order, leaving the
rest as blanks (`PLACEHOLDER`) -- the server already knows the exact
slot_pattern (word lengths, spaces, punctuation) for the puzzle being played,
so the client only ever sends the letters themselves, positionally, never the
shape. This also means a client can't smuggle an unrelated pattern past the
server: the regex is always built from *our* slot_pattern.

Design note: this was originally built on CirrusSearch's documented
`intitle:/regex/` feature (see Help:CirrusSearch on mediawiki.org). Live
testing against production en.wikipedia.org showed it does NOT reliably
filter to the regex -- queries like `intitle:/^Albert\\ ........$/i` came
back with plenty of titles that plainly don't match (e.g. "George VI") mixed
in with real matches, apparently falling back toward general relevance
search rather than a strict filter. Rather than depend on that, CirrusSearch
is used here only as a *candidate recall* step (a plain `intitle:` keyword
search on the known literal letter-runs), and the real match check is a
local Python regex applied to the results -- CirrusSearch narrows the field,
Python guarantees correctness.
"""

import logging
import re
from dataclasses import dataclass, field

import requests

from .mediawiki_api import MediaWikiClient

logger = logging.getLogger(__name__)

PLACEHOLDER = "_"
MAX_RESULTS = 20
CANDIDATE_FETCH_LIMIT = 50
MIN_LITERAL_RUN = 2  # shorter runs are too noisy to use as search keywords


@dataclass
class HintResult:
    titles: list[str] = field(default_factory=list)
    truncated: bool = False
    unavailable: bool = False


def _word_regex_fragments(slot_pattern: list[dict], pattern: str) -> list[str]:
    """Per-token regex fragments (before joining/anchoring), and separately
    the raw per-word letter chunks -- used by both the strict verification
    regex and the loose keyword-query builder below.
    """
    cursor = 0
    fragments: list[str] = []
    for token in slot_pattern:
        if token["type"] == "space":
            fragments.append(r"\ ")
        elif token["type"] == "punct":
            fragments.append(re.escape(token["char"]))
        else:
            length = token["len"]
            chunk = pattern[cursor : cursor + length]
            cursor += length
            for ch in chunk:
                fragments.append("." if ch == PLACEHOLDER else re.escape(ch))
    return fragments


def build_regex(slot_pattern: list[dict], pattern: str) -> str:
    """slot_pattern: Article.slot_pattern (word/space/punct tokens).
    pattern: a string whose length equals the total letter count across all
    'word' tokens -- each char is either a known letter or PLACEHOLDER.
    This is a plain Python `re` pattern (not CirrusSearch dialect) -- it's
    only ever evaluated locally, via re.fullmatch, never sent to the API.
    """
    if not re.fullmatch(r"[A-Za-z_]*", pattern):
        raise ValueError("pattern may only contain letters and '_' placeholders")
    return "^" + "".join(_word_regex_fragments(slot_pattern, pattern)) + "$"


def _candidate_query(slot_pattern: list[dict], pattern: str) -> str | None:
    """Builds a plain `intitle:"..."` keyword query from the longest
    contiguous run(s) of known (non-placeholder) letters, to fetch a
    candidate pool worth locally filtering. Returns None if there isn't
    enough known information to search on usefully.
    """
    cursor = 0
    runs: list[str] = []
    for token in slot_pattern:
        if token["type"] != "word":
            continue
        chunk = pattern[cursor : cursor + token["len"]]
        cursor += token["len"]
        for run in chunk.split(PLACEHOLDER):
            if len(run) >= MIN_LITERAL_RUN:
                runs.append(run)

    if not runs:
        return None
    longest = max(runs, key=len)
    return f'intitle:"{longest}"'


def search_titles_by_regex(client: MediaWikiClient, slot_pattern: list[dict], pattern: str) -> HintResult:
    query = _candidate_query(slot_pattern, pattern)
    if query is None:
        return HintResult(titles=[])

    try:
        data = client.search_intitle(query, limit=CANDIDATE_FETCH_LIMIT)
    except requests.RequestException:
        logger.warning("Hint search failed for query=%r", query, exc_info=True)
        return HintResult(unavailable=True)

    candidates = [item["title"] for item in data.get("query", {}).get("search", [])]

    verifier = re.compile(build_regex(slot_pattern, pattern), re.IGNORECASE)
    matches = [title for title in candidates if verifier.fullmatch(title)]

    return HintResult(titles=matches[:MAX_RESULTS], truncated=len(matches) > MAX_RESULTS)
