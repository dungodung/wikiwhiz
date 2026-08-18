"""Lexical closeness scoring: guess text vs. the answer title.

Normalize -> blend rapidfuzz token_sort_ratio (robust to word reordering,
important for multi-word titles) with plain character ratio (keeps the score
anchored to true character-level closeness) -> bucket into 20 discrete steps
for the frontend's blue(cold)->red(hot) gradient bar.
"""

import unicodedata

from rapidfuzz import fuzz

NUM_BUCKETS = 20


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    stripped = stripped.casefold()
    stripped = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in stripped)
    return " ".join(stripped.split())


def score_lexical(guess_text: str, answer_title: str) -> float:
    """Returns a raw similarity score in [0, 1]."""
    a = normalize_text(guess_text)
    b = normalize_text(answer_title)
    if not a or not b:
        return 0.0
    token_sort = fuzz.token_sort_ratio(a, b) / 100.0
    char_ratio = fuzz.ratio(a, b) / 100.0
    return 0.6 * token_sort + 0.4 * char_ratio


def bucket_lexical(raw_score: float) -> int:
    """Maps a [0,1] raw score to a 0..19 bucket (0=coldest/blue, 19=hottest/red)."""
    bucket = int(raw_score * NUM_BUCKETS)
    return min(NUM_BUCKETS - 1, max(0, bucket))
