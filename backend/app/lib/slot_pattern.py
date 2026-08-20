"""Turn a display title into a Wheel-of-Fortune-style tile shape.

The board is a single row of tiles, one per character of normalize_to_tiles()
-- every tile is a guessable blank, whether the real character underneath is
a letter or kept punctuation (space, dash, comma, parenthesis). Nothing about
the title's structure is pre-revealed: the player has to figure out both the
letters *and* where the spaces/dashes/commas/parens fall, by typing whichever
character they think belongs in a given tile. All other punctuation
(quotation marks, periods, apostrophes, colons, digits, diacritics) is
stripped entirely and never appears at all.

The pattern is computed once, at article-insert time, and stored as JSON
(a plain string) on Article.slot_pattern -- currently just 'L' repeated for
the tile count, kept as a string (not an int) so existing code that iterates
position-by-position keeps working if per-tile distinctions are reintroduced
later.
"""

import unicodedata

# Letters with no single-codepoint ASCII decomposition under NFKD -- handled
# manually so e.g. "Straße" and "Bjørn" don't silently lose a tile.
_TRANSLIT = {
    "æ": "ae", "Æ": "AE",
    "œ": "oe", "Œ": "OE",
    "ß": "ss",
    "ø": "o", "Ø": "O",
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th",
    "ł": "l", "Ł": "L",
}

# Punctuation kept as its own guessable tile -- structural, but never hidden
# or discarded. Everything else (quotation marks, periods, colons,
# apostrophes, digits, ...) is stripped by normalize_to_tiles.
KEPT_PUNCTUATION = " -,()"


def normalize_to_tiles(title: str) -> str:
    """Actual letters (case preserved) plus KEPT_PUNCTUATION characters --
    everything else (quotation marks, diacritics, other punctuation) is
    stripped. This is the canonical form compared against a player's
    filled-in guess.
    """
    transliterated = "".join(_TRANSLIT.get(ch, ch) for ch in title)
    decomposed = unicodedata.normalize("NFKD", transliterated)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_text if ch.isalpha() or ch in KEPT_PUNCTUATION)


def tile_shape(title: str) -> str:
    """One guessable 'L' tile per character of normalize_to_tiles() -- letter
    or kept punctuation alike. This is what Article.slot_pattern stores and
    what the frontend renders: nothing is revealed pre-win.
    """
    return "L" * len(normalize_to_tiles(title))
