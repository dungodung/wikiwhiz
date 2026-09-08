from unittest.mock import MagicMock

import pytest
import requests

from backend.app.lib.hint_search import (
    build_regex,
    search_titles_by_regex,
    verify_real_article,
)


def test_all_placeholders():
    assert build_regex("LLLL", "____") == "^....$"


def test_known_and_unknown_letters_in_any_order():
    # "Mars" guessed as M?r? -- known letters need not be contiguous or ordered
    assert build_regex("LLLL", "M_r_") == "^M.r.$"


def test_dash_is_escaped_literally_once_guessed():
    # Every tile is guessable now, including punctuation -- a correctly
    # guessed dash is just literal content in the pattern, same as a letter.
    assert build_regex("L" * 10, "Spider-Man") == r"^Spider\-Man$"


def test_rejects_wrong_length():
    with pytest.raises(ValueError):
        build_regex("LLLL", "___")


def test_rejects_invalid_characters():
    with pytest.raises(ValueError):
        build_regex("LLL", "a!_")


def test_allows_digits():
    assert build_regex("LL", "1_") == "^1.$"


def test_search_locally_filters_out_noisy_candidates():
    """Regression test: live testing against production en.wikipedia.org
    showed CirrusSearch's `intitle:/regex/` does NOT reliably filter to the
    regex -- it returned titles that plainly didn't match. search_titles_by_regex
    must locally re-verify every candidate (against its normalized, space-free
    tile form) before returning it.
    """
    slot_pattern = "LLLLLL LLLLLLLL"
    client = MagicMock()
    client.search_intitle.return_value = {
        "query": {
            "search": [
                {"title": "Albert Einstein"},  # real match: "Albert Einstein" (space kept)
                {"title": "George VI"},  # noise CirrusSearch actually returned
                {"title": "Albert Camus"},  # right first word, wrong total length -- must be filtered
            ]
        }
    }

    result = search_titles_by_regex(client, slot_pattern, "Albert " + "_" * 8)

    assert [m.title for m in result.matches] == ["Albert Einstein"]
    assert result.matches[0].tiles == "Albert Einstein"
    assert result.unavailable is False


def test_search_finds_a_fully_typed_redirect_via_direct_lookup():
    """Regression test: "Extremity" (9 letters) is a real redirect to
    "Extremities" (10 letters, a different shape entirely) -- typing out
    the whole word "EXTREMITY" never found it, even though it's a real,
    correctly-shaped article, because search_titles_by_regex only ever
    checked CirrusSearch candidates' own titles, never the redirecttitle
    that would have actually named it. A fully-specified pattern now goes
    through verify_real_article first (the same case-insensitive,
    redirect-aware lookup guess submission already relies on), which finds
    it via the search fallback's redirecttitle field.
    """
    client = MagicMock()
    client.resolve_title.return_value = None  # case-sensitivity miss, as it would live
    client.search_intitle.return_value = {
        "query": {"search": [{"title": "Extremities", "pageid": 1137728, "redirecttitle": "Extremity"}]}
    }

    result = search_titles_by_regex(client, "L" * 9, "EXTREMITY")

    assert [m.title for m in result.matches] == ["Extremity"]
    assert result.matches[0].tiles == "Extremity"


def test_search_finds_a_redirect_hit_via_redirecttitle_for_partial_pattern():
    """Same underlying gap as above, but for a still-in-progress guess
    (the general candidate loop, not the fully-typed direct-lookup path) --
    a hit whose own title doesn't fit the board at all can still be a real
    suggestion via its redirecttitle.
    """
    client = MagicMock()
    client.search_intitle.return_value = {
        "query": {"search": [{"title": "Extremities", "pageid": 1137728, "redirecttitle": "Extremity"}]}
    }

    result = search_titles_by_regex(client, "L" * 9, "EXTR_____")

    assert [m.title for m in result.matches] == ["Extremity"]


def test_search_returns_unavailable_on_network_failure():
    client = MagicMock()
    client.search_intitle.side_effect = requests.exceptions.HTTPError("429")

    result = search_titles_by_regex(client, "LLLL", "Ma__")
    assert result.unavailable is True


def test_search_with_no_known_letters_skips_the_api_call():
    client = MagicMock()

    result = search_titles_by_regex(client, "LLLL", "____")

    client.search_intitle.assert_not_called()
    assert result.matches == []


def test_verify_accepts_a_redirect_via_direct_title_lookup():
    """A redirect (e.g. a common alternate name, or a concatenated no-space
    variant) must count as a real article, not get discarded just because
    it isn't the canonical title -- client.resolve_title follows redirects,
    so this is checked first and definitively, before ever falling back to
    the fuzzier search-based recall.
    """
    client = MagicMock()
    client.resolve_title.return_value = {"pageid": 736, "title": "Albert Einstein"}

    result = verify_real_article(client, "AlbertEinstein")

    assert result.found is True
    assert result.pageid == 736
    assert result.title == "Albert Einstein"
    client.search_intitle.assert_not_called()


def test_verify_shows_the_redirect_not_the_target_via_direct_lookup():
    """Same display concern as the search-fallback version above
    (test_verify_accepts_a_redirect_guess_via_search_redirecttitle), but for
    a redirect caught by the *direct* exact-title lookup instead: resolve_title
    reports the original queried title as "redirected_from" whenever the
    query itself was a redirect page (see mediawiki_api.py), and that's what
    should be shown back to the player -- not the target title MediaWiki's
    response always carries in "title" regardless of redirect status.
    """
    client = MagicMock()
    client.resolve_title.return_value = {"pageid": 736, "title": "Albert Einstein", "redirected_from": "A. Einstein"}

    result = verify_real_article(client, "AEinstein")

    assert result.found is True
    assert result.pageid == 736
    assert result.title == "A. Einstein"


def test_verify_finds_a_match_via_search_when_direct_lookup_misses():
    """Spaces are preserved in a guess now (they're their own fixed, visible
    tile -- see lib/slot_pattern.py), so a properly-spaced guess of a real
    title usually resolves via the direct lookup above. But other stripped
    punctuation (e.g. an apostrophe) can still make the flattened guess
    differ from the real title text, so the direct exact-title lookup can
    still miss -- this is what the search fallback is for.
    """
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.return_value = {
        "query": {"search": [{"title": "O'Brien Industries", "pageid": 4242}]}
    }

    result = verify_real_article(client, "OBrien Industries")

    assert result.found is True
    assert result.pageid == 4242
    assert result.title == "O'Brien Industries"


def test_verify_accepts_a_redirect_guess_via_search_redirecttitle():
    """Regression test: the tile board only ever sends uppercase (TileBoard.jsx
    forces every character upper-case), so the direct exact-title lookup --
    case-sensitive beyond a title's first letter -- routinely misses a real
    redirect page (e.g. "MONKEYS" as a literal title lookup misses "Monkeys").
    CirrusSearch's normal `list=search` also can't help by itself: when a
    query matches via a redirect, the hit's own "title"/"pageid" are the
    *target* article's, not the redirect's, so comparing that title against
    the guess's own (redirect) spelling never matches either. The
    `redirecttitle` prop is what actually carries the redirect's own title,
    letting verify_real_article recognize the guess.

    The returned pageid is still the *target*'s (55, "Monkey") -- that's the
    real graph node degrees/scoring need -- but the returned title is the
    redirect's own ("Monkeys"), not the target's: this is what the game
    displays back to the player in the guess history, and it should show
    the page they actually typed, not one they never guessed (see
    test_redirect_guess_display_shows_the_redirect_not_the_target in
    test_routes_game.py for the end-to-end version of this).
    """
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.return_value = {
        "query": {
            "search": [{"title": "Monkey", "pageid": 55, "redirecttitle": "Monkeys"}],
        }
    }

    result = verify_real_article(client, "MONKEYS")

    assert result.found is True
    assert result.pageid == 55
    assert result.title == "Monkeys"


def test_verify_search_fallback_queries_the_whole_guess_as_one_phrase():
    """Regression test: an earlier version of this fallback split the guess
    into small prefix/suffix windows (e.g. "MON"/"EYS"/"KEYS" for "MONKEYS"),
    which a live check found actively hides the correct hit -- those tiny
    fragments match tens of thousands of unrelated articles, pushing the
    real target out of the top CANDIDATE_FETCH_LIMIT results, while
    searching the exact, unsplit phrase puts it first. A fully-specified
    guess already has its real spaces in it, so the whole phrase is already
    word-aligned -- there's no mid-word-slice risk windowing was guarding
    against in the first place.
    """
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.return_value = {"query": {"search": []}}

    verify_real_article(client, "MONKEYS")

    client.search_intitle.assert_called_once()
    (query,), _ = client.search_intitle.call_args
    assert query == 'intitle:"MONKEYS" OR "MONKEYS"'


def test_verify_falls_back_to_search_when_no_exact_title_or_redirect_exists():
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.return_value = {
        "query": {"search": [{"title": "Albert Einstein", "pageid": 736}, {"title": "Noise", "pageid": 1}]}
    }

    result = verify_real_article(client, "Albert Einstein")

    assert result.found is True
    assert result.pageid == 736
    assert result.title == "Albert Einstein"


def test_verify_rejects_gibberish_no_candidate_matches():
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.return_value = {"query": {"search": [{"title": "Unrelated Article", "pageid": 2}]}}

    result = verify_real_article(client, "TotallyMadeUpXX")

    assert result.found is False
    assert result.unavailable is False


def test_verify_degrades_gracefully_when_direct_lookup_fails():
    client = MagicMock()
    client.resolve_title.side_effect = requests.exceptions.HTTPError("429")

    result = verify_real_article(client, "AlbertEinstein")

    assert result.unavailable is True
    assert result.found is False
    client.search_intitle.assert_not_called()


def test_verify_degrades_gracefully_when_search_fallback_fails():
    client = MagicMock()
    client.resolve_title.return_value = None
    client.search_intitle.side_effect = requests.exceptions.HTTPError("429")

    result = verify_real_article(client, "AlbertEinstein")

    assert result.unavailable is True
    assert result.found is False


def test_verify_skips_the_search_fallback_for_very_short_guesses():
    client = MagicMock()
    client.resolve_title.return_value = None

    result = verify_real_article(client, "AB")

    client.search_intitle.assert_not_called()
    assert result.found is False
