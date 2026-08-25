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


# Below this length the search fallback isn't worth calling -- too short a
# phrase mostly returns noise, and check_guess_shape already rejects an
# empty/near-empty guess before verify_real_article is ever reached anyway.
MIN_VERIFY_SEARCH_LENGTH = 3


def verify_real_article(client: MediaWikiClient, guess_tiles: str) -> VerifyResult:
    """Best-effort confirmation that a fully-filled-in guess spells some real
    enwiki article, used to reject gibberish guesses before they consume an
    attempt (see game/service.py::process_guess).

    Tries an exact title lookup first (client.resolve_title, which follows
    redirects) -- in principle the definitive check, since a common
    alternate name or a concatenated no-space variant (e.g. an initialism
    redirect) often exactly equals the flattened guess. In practice this
    almost never fires for a *redirect* guess: the tile board only ever
    sends uppercase (TileBoard.jsx forces every typed character to
    upper-case), and MediaWiki only auto-capitalizes a title's first
    letter -- `titles=MONKEYS` looks up the literal page "MONKEYS", not
    "Monkeys", and misses. It's harmless for the *canonical* title of
    whatever the guess resolves to, since that always gets independently
    re-confirmed by the fallback search below regardless -- but a redirect
    with no canonical-cased fallback route needs that fallback to actually
    recognize it, which is what the redirecttitle check below is for.

    The fallback searches the *whole* guess as one phrase (`intitle:` plus
    an unrestricted OR, same pattern as _candidate_query in
    search_titles_by_regex, so a match reached only through a redirect's
    indexed text still surfaces) rather than splitting it into smaller
    prefix/suffix windows the way an earlier version of this function did.
    That windowing was built for the wrong problem: it was worried about a
    slice landing mid-word, but a fully-specified guess already has its
    real (player-typed) spaces in it, so the whole phrase is already
    word-aligned -- there's nothing left for windowing to fix, and live
    testing found it actively hides the correct hit: querying "MONKEYS"
    split into fragments like "MON"/"EYS"/"KEYS" pulls in tens of
    thousands of unrelated articles that happen to contain one of those
    fragments, pushing "Monkey" (a real redirect target) out of the top 50
    results entirely, while the exact, unsplit phrase "MONKEYS" puts it in
    first place.

    A hit is accepted either of two ways: its own title matches the guess
    (the normalize_to_tiles() equality check search_titles_by_regex also
    uses), or -- the case a redirect guess actually needs -- CirrusSearch's
    `redirecttitle` prop says the query matched via one of the hit's
    incoming redirects, and that redirect's own title is what the guess
    spells (case-insensitively, for the same reason the exact lookup above
    can't be relied on). A search hit's `title`/`pageid` are always the
    *target* page's own identity even when matched via redirecttitle, never
    the redirect's -- exactly the resolved title/pageid a redirect guess
    should score against. This can still, in principle, reject a genuinely
    real title CirrusSearch just doesn't surface within CANDIDATE_FETCH_LIMIT
    results -- but it will never accept a fake one, since acceptance always
    requires an exact tile match either way.
    """
    try:
        direct = client.resolve_title(guess_tiles)
    except requests.RequestException:
        logger.warning("Guess verification lookup failed for guess_tiles=%r", guess_tiles, exc_info=True)
        return VerifyResult(unavailable=True)
    if direct is not None:
        # Show the player back the page they actually typed, not its
        # redirect target -- resolved_pageid (used for scoring/degrees)
        # stays the target's regardless; only the *display* title changes.
        return VerifyResult(pageid=direct["pageid"], title=direct.get("redirected_from") or direct["title"])

    if len(guess_tiles) < MIN_VERIFY_SEARCH_LENGTH:
        return VerifyResult()

    query = f'intitle:"{guess_tiles}" OR "{guess_tiles}"'
    try:
        data = client.search_intitle(query, limit=CANDIDATE_FETCH_LIMIT)
    except requests.RequestException:
        logger.warning("Guess verification search failed for guess_tiles=%r", guess_tiles, exc_info=True)
        return VerifyResult(unavailable=True)

    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        if normalize_to_tiles(title).lower() == guess_tiles.lower():
            return VerifyResult(pageid=item["pageid"], title=title)
        redirect_title = item.get("redirecttitle")
        if redirect_title and normalize_to_tiles(redirect_title).lower() == guess_tiles.lower():
            # Same reasoning as the direct-lookup branch above: pageid
            # stays the target's for scoring, but what the player sees
            # should be the redirect page they actually typed.
            return VerifyResult(pageid=item["pageid"], title=redirect_title)

    return VerifyResult()
