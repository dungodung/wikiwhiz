from unittest.mock import MagicMock

from backend.app.lib.mediawiki_api import MediaWikiClient


def _client_with_responses(responses):
    client = MediaWikiClient(user_agent="test-agent")
    client.session = MagicMock()
    client.session.get.side_effect = [
        MagicMock(status_code=200, json=lambda r=r: r, raise_for_status=lambda: None) for r in responses
    ]
    return client


def test_titles_to_pageids_chunks_past_fifty():
    """Regression coverage for the chunking behavior that used to live
    inline in degrees.py/precompute_link_cache.py (see
    test_degrees.py::test_compute_degrees_live_resolves_all_neighbors_past_the_first_50)
    and now lives here: a batch of more than 50 titles must be split into
    multiple 50-title API calls, with every title's pageid present in the
    merged result -- not just the first chunk's.
    """
    titles = [f"Filler Title {i}" for i in range(59)] + ["George H W Bush"]
    first_chunk_pages = {
        str(1000 + i): {"pageid": 1000 + i, "title": title} for i, title in enumerate(titles[:50])
    }
    second_chunk_pages = {
        "200": {"pageid": 200, "title": "George H W Bush"},
        **{str(1050 + i): {"pageid": 1050 + i, "title": title} for i, title in enumerate(titles[50:59])},
    }
    client = _client_with_responses(
        [{"query": {"pages": first_chunk_pages}}, {"query": {"pages": second_chunk_pages}}]
    )

    result = client.titles_to_pageids(titles)

    assert client.session.get.call_count == 2
    assert result["George H W Bush"] == 200
    assert len(result) == 60


def test_titles_to_pageids_omits_missing_titles():
    client = _client_with_responses(
        [
            {
                "query": {
                    "pages": {
                        "-1": {"title": "Nonexistent Page", "missing": ""},
                        "42": {"pageid": 42, "title": "Real Page"},
                    }
                }
            }
        ]
    )

    result = client.titles_to_pageids(["Nonexistent Page", "Real Page"])

    assert result == {"Real Page": 42}


def test_pageids_to_titles_chunks_past_fifty():
    pageids = list(range(1, 61))
    first_chunk_pages = {str(pid): {"pageid": pid, "title": f"Title {pid}"} for pid in pageids[:50]}
    second_chunk_pages = {str(pid): {"pageid": pid, "title": f"Title {pid}"} for pid in pageids[50:]}
    client = _client_with_responses(
        [{"query": {"pages": first_chunk_pages}}, {"query": {"pages": second_chunk_pages}}]
    )

    result = client.pageids_to_titles(pageids)

    assert client.session.get.call_count == 2
    assert len(result) == 60
    assert result[60] == "Title 60"


def test_prefix_search_excludes_redirects_and_disambiguation_pages():
    """The admin add-article popup's autocomplete -- neither a redirect nor
    a disambiguation page is ever a valid answer (see prefix_search's own
    docstring), so both must be filtered out even though the raw
    generator=prefixsearch response includes them.
    """
    pages = {
        "1": {"pageid": 1, "title": "Real Article", "index": 1},
        "2": {"pageid": 2, "title": "A Redirect", "index": 2, "redirect": ""},
        "3": {"pageid": 3, "title": "A Disambiguation Page", "index": 3, "pageprops": {"disambiguation": ""}},
        "4": {"pageid": 4, "title": "Another Real Article", "index": 4},
    }
    client = _client_with_responses([{"query": {"pages": pages}}])

    result = client.prefix_search("Real", limit=8)

    assert [r["title"] for r in result] == ["Real Article", "Another Real Article"]


def test_prefix_search_preserves_relevance_order():
    """query.pages is a dict keyed by pageid -- not guaranteed to iterate in
    request order, so ordering must come from each page's own `index`
    rather than dict insertion order.
    """
    pages = {
        "3": {"pageid": 3, "title": "Third", "index": 3},
        "1": {"pageid": 1, "title": "First", "index": 1},
        "2": {"pageid": 2, "title": "Second", "index": 2},
    }
    client = _client_with_responses([{"query": {"pages": pages}}])

    result = client.prefix_search("T", limit=8)

    assert [r["title"] for r in result] == ["First", "Second", "Third"]
