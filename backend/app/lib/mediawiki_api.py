"""Thin requests-based wrapper around the English Wikipedia Action API.

Plain `requests` is used rather than pywikibot: wikiwhiz never edits anything,
it only issues read-only `action=query`/`action=parse` calls, so pywikibot's
authenticated-edit-session machinery would be pure overhead here. Per the
wikimedia-api-access convention, every request carries a descriptive
User-Agent.
"""

import time

import requests

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_DEFAULT_TIMEOUT = 10
_MAX_429_RETRIES = 3


def now() -> float:
    return time.monotonic()


class MediaWikiClient:
    def __init__(self, user_agent: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def query(self, params: dict, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        """A sustained precompute run (many hundreds of sequential requests
        for a hub-heavy article) can trip Wikimedia's anonymous-client rate
        limit -- confirmed live, not theoretical: a 429 killed a precompute
        run outright before this retry was added. Backs off honoring
        Retry-After when the server sends one, otherwise a short fixed
        delay; gives up after _MAX_429_RETRIES so a persistent block still
        surfaces as an error rather than hanging.
        """
        params = {**params, "action": "query", "format": "json"}
        for attempt in range(_MAX_429_RETRIES + 1):
            resp = self.session.get(WIKIPEDIA_API, params=params, timeout=timeout)
            if resp.status_code == 429 and attempt < _MAX_429_RETRIES:
                delay = float(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()

    def query_all(self, params: dict, timeout: float = _DEFAULT_TIMEOUT, max_pages: int | None = None):
        """Generator that follows `continue` tokens, yielding each response's
        'query' dict in turn. Caller merges whichever sub-keys it needs.

        max_pages bounds how many continuation round-trips this call will
        make before giving up on the rest. Needed because a single batched
        prop=links/linkshere query continues page-by-page through whichever
        pageid in the batch has the most links before moving to the next --
        for a real hub article (a landmark like the Eiffel Tower, linked
        from thousands of "list of..." articles) that can be hundreds of
        sequential round-trips for one BFS frontier, effectively hanging the
        caller. Bounded callers accept a partial link list for that node
        rather than exhaustively draining it.
        """
        params = dict(params)
        pages_fetched = 0
        while True:
            data = self.query(params, timeout=timeout)
            yield data.get("query", {})
            pages_fetched += 1
            if "continue" not in data:
                return
            if max_pages is not None and pages_fetched >= max_pages:
                return
            params.update(data["continue"])

    def resolve_title(self, title: str, timeout: float = _DEFAULT_TIMEOUT) -> dict | None:
        """Exact title lookup, following redirects -- so a redirect page
        (e.g. a common alternate name or a concatenated-no-space variant)
        resolves straight to its real target rather than being missed.
        Returns {"pageid", "title"} (the target's, if title was a redirect)
        or None if no page or redirect exists under that exact title.
        """
        data = self.query({"titles": title, "redirects": 1}, timeout=timeout)
        pages = data.get("query", {}).get("pages", {})
        for pageid, page in pages.items():
            if pageid == "-1" or "missing" in page:
                continue
            return {"pageid": int(pageid), "title": page["title"]}
        return None

    def titles_to_pageids(self, titles: list[str], timeout: float = _DEFAULT_TIMEOUT) -> dict[str, int]:
        """Batch title -> pageid, for titles that exist as real pages. No
        redirect following (unlike resolve_title above) -- a redirect page
        resolves to its own pageid here, not its target's, matching how BFS
        neighbor titles have always been resolved in degrees.py/
        precompute_link_cache.py. Missing/invalid titles are simply absent
        from the result rather than raising, since a BFS frontier routinely
        includes red-link titles that don't correspond to any real page.
        """
        out: dict[str, int] = {}
        titles_list = list(titles)
        for chunk_start in range(0, len(titles_list), 50):
            chunk = titles_list[chunk_start : chunk_start + 50]
            data = self.query({"titles": "|".join(chunk)}, timeout=timeout)
            pages = data.get("query", {}).get("pages", {})
            for pageid_str, page in pages.items():
                if pageid_str == "-1" or "missing" in page:
                    continue
                out[page["title"]] = int(pageid_str)
        return out

    def pageids_to_titles(self, pageids: list[int], timeout: float = _DEFAULT_TIMEOUT) -> dict[int, str]:
        """Batch pageid -> title, for pageids that still exist."""
        out: dict[int, str] = {}
        pageids_list = list(pageids)
        for chunk_start in range(0, len(pageids_list), 50):
            chunk = pageids_list[chunk_start : chunk_start + 50]
            data = self.query({"pageids": "|".join(str(p) for p in chunk)}, timeout=timeout)
            pages = data.get("query", {}).get("pages", {})
            for pageid_str, page in pages.items():
                if pageid_str == "-1" or "missing" in page:
                    continue
                out[int(pageid_str)] = page["title"]
        return out

    def search_intitle(self, query: str, limit: int = 50, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        """Plain CirrusSearch `intitle:` keyword search -- used as the
        candidate-recall step for hint-mode autocomplete. See
        backend/app/lib/hint_search.py for why this isn't a regex search:
        CirrusSearch's `intitle:/regex/` feature did not, in live testing,
        reliably filter results to the regex (returned plenty of titles that
        didn't match at all), so it's used here only to narrow the field;
        the real match check is a local Python regex over the results.
        """
        return self.query(
            {
                "list": "search",
                "srsearch": query,
                "srnamespace": 0,
                "srlimit": limit,
                "srprop": "",
            },
            timeout=timeout,
        )

    def links_batch(
        self, pageids: list[int], timeout: float = _DEFAULT_TIMEOUT, max_continuation_pages: int | None = None
    ) -> dict[int, set[str]]:
        """Outgoing links (namespace 0) for up to 50 pageids at a time."""
        out: dict[int, set[str]] = {pid: set() for pid in pageids}
        for chunk_start in range(0, len(pageids), 50):
            chunk = pageids[chunk_start : chunk_start + 50]
            for query in self.query_all(
                {
                    "prop": "links",
                    "pageids": "|".join(str(p) for p in chunk),
                    "plnamespace": 0,
                    "pllimit": "max",
                },
                timeout=timeout,
                max_pages=max_continuation_pages,
            ):
                for pageid_str, page in query.get("pages", {}).items():
                    pageid = int(pageid_str)
                    for link in page.get("links", []):
                        out.setdefault(pageid, set()).add(link["title"])
        return out

    def linkshere_batch(
        self, pageids: list[int], timeout: float = _DEFAULT_TIMEOUT, max_continuation_pages: int | None = None
    ) -> dict[int, set[str]]:
        """Incoming links (namespace 0) for up to 50 pageids at a time."""
        out: dict[int, set[str]] = {pid: set() for pid in pageids}
        for chunk_start in range(0, len(pageids), 50):
            chunk = pageids[chunk_start : chunk_start + 50]
            for query in self.query_all(
                {
                    "prop": "linkshere",
                    "pageids": "|".join(str(p) for p in chunk),
                    "lhnamespace": 0,
                    "lhlimit": "max",
                },
                timeout=timeout,
                max_pages=max_continuation_pages,
            ):
                for pageid_str, page in query.get("pages", {}).items():
                    pageid = int(pageid_str)
                    for link in page.get("linkshere", []):
                        out.setdefault(pageid, set()).add(link["title"])
        return out
