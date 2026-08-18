from unittest.mock import MagicMock

import pytest
import requests

from backend.app.lib.hint_search import build_regex, search_titles_by_regex


def test_single_word_all_placeholders():
    slot_pattern = [{"type": "word", "len": 4}]
    assert build_regex(slot_pattern, "____") == "^....$"


def test_known_and_unknown_letters_mixed_and_in_any_order():
    # "Mars" guessed as M?r? -- known letters need not be contiguous or ordered
    slot_pattern = [{"type": "word", "len": 4}]
    assert build_regex(slot_pattern, "M_r_") == "^M.r.$"


def test_multi_word_with_space_token():
    slot_pattern = [{"type": "word", "len": 6}, {"type": "space"}, {"type": "word", "len": 8}]
    regex = build_regex(slot_pattern, "Albert__" + "________")
    assert regex.startswith("^Albert")
    assert r"\ " in regex
    assert regex.endswith("$")


def test_punctuation_token_is_escaped_literally():
    slot_pattern = [
        {"type": "word", "len": 6},
        {"type": "punct", "char": "-"},
        {"type": "word", "len": 3},
    ]
    regex = build_regex(slot_pattern, "Spider" + "Man")
    assert regex == r"^Spider\-Man$"


def test_rejects_invalid_characters():
    slot_pattern = [{"type": "word", "len": 3}]
    with pytest.raises(ValueError):
        build_regex(slot_pattern, "a1_")


def test_search_locally_filters_out_noisy_candidates():
    """Regression test: live testing against production en.wikipedia.org
    showed CirrusSearch's `intitle:/regex/` does NOT reliably filter to the
    regex -- it returned titles that plainly didn't match (e.g. "George VI"
    for a pattern requiring "Albert " + 8 letters). search_titles_by_regex
    must locally re-verify every candidate before returning it.
    """
    slot_pattern = [{"type": "word", "len": 6}, {"type": "space"}, {"type": "word", "len": 8}]
    client = MagicMock()
    client.search_intitle.return_value = {
        "query": {
            "search": [
                {"title": "Albert Einstein"},  # real match
                {"title": "George VI"},  # noise CirrusSearch actually returned
                {"title": "Albert Camus"},  # right first word, wrong second-word length -- must be filtered
            ]
        }
    }

    result = search_titles_by_regex(client, slot_pattern, "Albert__" + "________")

    assert result.titles == ["Albert Einstein"]
    assert result.unavailable is False


def test_search_returns_unavailable_on_network_failure():
    slot_pattern = [{"type": "word", "len": 4}]
    client = MagicMock()
    client.search_intitle.side_effect = requests.exceptions.HTTPError("429")

    result = search_titles_by_regex(client, slot_pattern, "Ma__")
    assert result.unavailable is True


def test_search_with_no_known_letters_skips_the_api_call():
    slot_pattern = [{"type": "word", "len": 4}]
    client = MagicMock()

    result = search_titles_by_regex(client, slot_pattern, "____")

    client.search_intitle.assert_not_called()
    assert result.titles == []
