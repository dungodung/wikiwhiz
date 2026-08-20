"""Hint-mode autocomplete: turn a partially-filled tile pattern into real
Wikipedia title suggestions.

The board is a single flat row of tiles (see lib/slot_pattern.py) -- every
tile is guessable, letters and kept punctuation (space, dash, comma, paren)
alike, and nothing is pre-revealed. The pattern sent here is whatever the
player has actually typed so far: a real character wherever they've filled
a tile, PLACEHOLDER everywhere else.

Design note: this was originally built on CirrusSearch's documented
`intitle:/regex/` feature. Live testing against production en.wikipedia.org
showed it does NOT reliably filter to the regex -- queries came back with
plenty of titles that plainly don't match, apparently falling back toward
general relevance search rather than a strict filter. CirrusSearch is used
here only as a *candidate recall* step (a plain `intitle:` keyword search on
the longest known letter run), and the real match check is a local Python
regex applied to each candidate's normalize_to_tiles() form -- CirrusSearch
narrows the field, Python guarantees correctness. Since spaces are stripped
before comparison, a known letter run that happens to span where a real
title's word break falls is still a literal substring of the normalized
title even though it isn't necessarily a literal substring of the raw
(spaced) title -- the recall query is best-effort regardless, correctness
never depends on it.
"""

import logging
import re
from dataclasses import dataclass, field

import requests

from .mediawiki_api import MediaWikiClient
from .slot_pattern import KEPT_PUNCTUATION, normalize_to_tiles

logger = logging.getLogger(__name__)

PLACEHOLDER = "_"
MAX_RESULTS = 20
CANDIDATE_FETCH_LIMIT = 50
MIN_LITERAL_RUN = 2  # shorter runs are too noisy to use as search keywords


@dataclass
class HintMatch:
    title: str
    tiles: str


@dataclass
class HintResult:
    matches: list[HintMatch] = field(default_factory=list)
    truncated: bool = False
    unavailable: bool = False


@dataclass
class VerifyResult:
    pageid: int | None = None
    title: str | None = None
    unavailable: bool = False

    @property
    def found(self) -> bool:
        return self.pageid is not None


def _validate(slot_pattern: str, pattern: str) -> None:
    if len(pattern) != len(slot_pattern):
        raise ValueError("pattern length must match the puzzle's tile count")
    for ch in pattern:
        if ch != PLACEHOLDER and not (ch.isalpha() or ch in KEPT_PUNCTUATION):
            raise ValueError("tiles may only contain letters, kept punctuation, or '_'")


def build_regex(slot_pattern: str, pattern: str) -> str:
    """Regex evaluated locally (via re.fullmatch) against a candidate title's
    normalize_to_tiles() form -- never sent to the API.
    """
    _validate(slot_pattern, pattern)
    fragments = []
    for ch in pattern:
        if ch == PLACEHOLDER:
            fragments.append(".")
        else:
            fragments.append(re.escape(ch))
    return "^" + "".join(fragments) + "$"


def _candidate_query(pattern: str) -> str | None:
    """Longest contiguous run of known characters (only a placeholder breaks
    a run -- a correctly-guessed space/dash/comma/paren is real content, not
    a gap, so it stays part of the run), used as a candidate-recall query to
    fetch a pool worth locally filtering. None if nothing usable is known.

    Combines a title-field search with a plain (unrestricted) phrase search:
    `intitle:` alone can miss a page reached only via a redirect (CirrusSearch
    scopes `intitle:` to the page's own title field), while the unrestricted
    phrase form also matches through a page's indexed redirect titles -- so a
    known run that happens to spell a common alternate name still surfaces
    the real target article as a suggestion.
    """
    runs = [run for run in pattern.split(PLACEHOLDER) if len(run) >= MIN_LITERAL_RUN]
    if not runs:
        return None
    longest = max(runs, key=len)
    return f'intitle:"{longest}" OR "{longest}"'


def search_titles_by_regex(client: MediaWikiClient, slot_pattern: str, pattern: str) -> HintResult:
    query = _candidate_query(pattern)
    if query is None:
        return HintResult()

    try:
        data = client.search_intitle(query, limit=CANDIDATE_FETCH_LIMIT)
    except requests.RequestException:
        logger.warning("Hint search failed for query=%r", query, exc_info=True)
        return HintResult(unavailable=True)

    candidates = [item["title"] for item in data.get("query", {}).get("search", [])]

    verifier = re.compile(build_regex(slot_pattern, pattern), re.IGNORECASE)
    matches = [
        HintMatch(title=title, tiles=normalize_to_tiles(title))
        for title in candidates
        if verifier.fullmatch(normalize_to_tiles(title))
    ]

    return HintResult(matches=matches[:MAX_RESULTS], truncated=len(matches) > MAX_RESULTS)


# Prefix/suffix lengths tried for candidate recall on a fully-specified
# guess. A guess has no placeholders left, so there's no natural known-run
# to anchor on the way hint search has -- but position 0 is *always* the
# start of the real first word (whatever it turns out to be), and the last
# character is *always* the end of the real last word, regardless of where
# internal word breaks fall. Trying every length in this range from both
# ends means one of them typically lands on an exact whole word, which
# CirrusSearch's phrase matching strongly favors -- confirmed live: for
# "ALBERT EINSTEIN" a mid-string slice like "ALBERT E" or "INSTEIN" (not a
# whole word) fails to surface "Albert Einstein" at all, while the exact
# 6-char prefix "ALBERT" does. This replaced an earlier dense-sliding-window
# design that (a) generated windows straddling word boundaries as often as
# landing on them and (b) once combined into one OR query past ~25-30
# clauses, made CirrusSearch silently return zero results rather than an
# error -- both confirmed live, not theoretical.
MIN_VERIFY_WINDOW = 3
MAX_VERIFY_WINDOW = 10


def _verify_candidate_windows(guess_tiles: str) -> list[str]:
    windows: list[str] = []
    seen: set[str] = set()
    upper = min(MAX_VERIFY_WINDOW, len(guess_tiles))
    for size in range(MIN_VERIFY_WINDOW, upper + 1):
        for window in (guess_tiles[:size], guess_tiles[-size:]):
            key = window.lower()
            if key not in seen:
                seen.add(key)
                windows.append(window)
    return windows


def verify_real_article(client: MediaWikiClient, guess_tiles: str) -> VerifyResult:
    """Best-effort confirmation that a fully-filled-in guess spells some real
    enwiki article, used to reject gibberish guesses before they consume an
    attempt (see game/service.py::process_guess).

    Tries an exact title lookup first (client.resolve_title, which follows
    redirects) -- this is the *definitive* check, and it's the one that
    matters most for redirects: a common alternate name or a concatenated
    no-space variant (e.g. an initialism redirect) often exactly equals the
    flattened guess, and must count as a real answer, not get discarded just
    because it isn't the canonical title.

    Only if that exact lookup misses does this fall back to a multi-length
    prefix/suffix search (see _verify_candidate_windows) plus the same
    normalize_to_tiles() equality check search_titles_by_regex uses for
    correctness. This can still, in principle, reject a genuinely real title
    if none of the tried windows happen to land on a real word -- but it
    will never accept a fake one, since acceptance always requires an exact
    tile match.
    """
    try:
        direct = client.resolve_title(guess_tiles)
    except requests.RequestException:
        logger.warning("Guess verification lookup failed for guess_tiles=%r", guess_tiles, exc_info=True)
        return VerifyResult(unavailable=True)
    if direct is not None:
        return VerifyResult(pageid=direct["pageid"], title=direct["title"])

    windows = _verify_candidate_windows(guess_tiles)
    if not windows:
        return VerifyResult()

    query = " OR ".join(f'"{w}"' for w in windows)
    try:
        data = client.search_intitle(query, limit=CANDIDATE_FETCH_LIMIT)
    except requests.RequestException:
        logger.warning("Guess verification search failed for guess_tiles=%r", guess_tiles, exc_info=True)
        return VerifyResult(unavailable=True)

    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        if normalize_to_tiles(title).lower() == guess_tiles.lower():
            return VerifyResult(pageid=item["pageid"], title=title)

    return VerifyResult()
