from unittest.mock import MagicMock

import pytest
import requests

from backend.app.lib.hint_search import (
    _verify_candidate_windows,
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
        build_regex("LLL", "a1_")


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


def test_verify_finds_a_match_via_sliding_window_when_direct_lookup_misses():
    """Spaces are preserved in a guess now (they're their own fixed, visible
    tile -- see lib/slot_pattern.py), so a properly-spaced guess of a real
    title usually resolves via the direct lookup above. But other stripped
    punctuation (e.g. an apostrophe) can still make the flattened guess
    differ from the real title text, so the direct exact-title lookup can
    still miss -- this is what the sliding-window search is for.
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


def test_verify_candidate_windows_include_whole_first_and_last_word():
    """Regression test: a live check confirmed CirrusSearch's phrase
    matching strongly favors whole words -- a mid-string slice like
    "ALBERT E" or "INSTEIN" (spanning or falling short of a real word)
    failed to surface "Albert Einstein" at all, while the exact 6-char
    prefix "ALBERT" and 8-char suffix "EINSTEIN" did. Multiple prefix/suffix
    lengths are tried specifically so one of them lands on the exact word.
    """
    windows = _verify_candidate_windows("ALBERT EINSTEIN")
    assert "ALBERT" in windows
    assert "EINSTEIN" in windows


def test_verify_candidate_windows_stay_within_query_complexity_limits():
    """Regression test: a live check confirmed that once an OR-combined
    CirrusSearch query passes somewhere around 25-30 clauses, it silently
    returns zero results instead of erroring -- an earlier dense
    sliding-window design could generate 30+ windows for a single guess and
    hit this. The prefix/suffix design is bounded by construction (two
    windows per length, MIN_VERIFY_WINDOW..MAX_VERIFY_WINDOW), so this stays
    well under that regardless of guess length.
    """
    windows = _verify_candidate_windows("ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMN")
    assert len(windows) <= 16


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
