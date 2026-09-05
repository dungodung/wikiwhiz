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
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_DEFAULT_TIMEOUT = 10
_MAX_429_RETRIES = 3


def now() -> float:
    return time.monotonic()


class MediaWikiClient:
    def __init__(self, user_agent: str, session: requests.Session | None = None, base_url: str = WIKIPEDIA_API):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.base_url = base_url

    def query(self, params: dict, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        """A sustained precompute run (many hundreds of sequential requests
        for a hub-heavy article) can trip Wikimedia's anonymous-client rate
        limit -- confirmed live, not theoretical: a 429 killed a precompute
        run outright before this retry was added. Backs off honoring
        Retry-After when the server sends one, otherwise a short fixed
        delay; gives up after _MAX_429_RETRIES so a persistent block still
        surfaces as an error rather than hanging.
        """
        params = {"action": "query", **params, "format": "json"}
        for attempt in range(_MAX_429_RETRIES + 1):
            resp = self.session.get(self.base_url, params=params, timeout=timeout)
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
        Returns {"pageid", "title", "redirected_from"} (the target's pageid
        and title; "redirected_from" is the queried title itself if it was
        a redirect page, else None -- callers that display a guess back to
        the player want the page they actually typed, not silently swapped
        for its target, see hint_search.verify_real_article) or None if no
        page or redirect exists under that exact title.
        """
        data = self.query({"titles": title, "redirects": 1}, timeout=timeout)
        redirected_from = None
        redirects = data.get("query", {}).get("redirects")
        if redirects:
            redirected_from = redirects[0]["from"]
        pages = data.get("query", {}).get("pages", {})
        for pageid, page in pages.items():
            if pageid == "-1" or "missing" in page:
                continue
            return {"pageid": int(pageid), "title": page["title"], "redirected_from": redirected_from}
        return None

    def prefix_search(self, query: str, limit: int = 8, timeout: float = _DEFAULT_TIMEOUT) -> list[dict]:
        """Title autocomplete for the admin add-article popup, namespace 0
        only, excluding redirects and disambiguation pages -- neither can
        ever be a valid answer (a redirect isn't a real article in its own
        right, and a disambiguation page has no single subject for clues to
        describe), so there's no point offering them as picks here. This is
        specific to *this* lookup, the content-authoring one -- the
        in-game player-facing search (hint_search.py) is a different
        method/endpoint entirely and is deliberately untouched by this: a
        player's wrong guess resolving to a redirect is a real, intended
        game mechanic (see game/service.py's redirect-to-answer handling),
        not a content-authoring mistake to filter out.

        Plain `list=prefixsearch` can't distinguish these, so this uses
        `generator=prefixsearch` instead (combinable with `prop=info` for
        the `redirect` flag and `prop=pageprops` for `disambiguation`).
        Over-fetches to compensate for filtered-out results, since
        gpslimit is capped at the raw candidate count before filtering,
        not the count after.
        """
        data = self.query(
            {
                "generator": "prefixsearch",
                "gpssearch": query,
                "gpslimit": min(limit * 3, 50),
                "gpsnamespace": 0,
                "prop": "info|pageprops",
                "ppprop": "disambiguation",
            },
            timeout=timeout,
        )
        pages = data.get("query", {}).get("pages", {})
        candidates = sorted(pages.values(), key=lambda page: page.get("index", 0))
        results = [
            {"title": page["title"], "pageid": page["pageid"]}
            for page in candidates
            if "redirect" not in page and "disambiguation" not in page.get("pageprops", {})
        ]
        return results[:limit]

    def get_wikibase_item(self, title: str, timeout: float = _DEFAULT_TIMEOUT) -> str | None:
        """The Wikidata QID linked from this enwiki article's page, if any."""
        data = self.query({"titles": title, "prop": "pageprops", "ppprop": "wikibase_item"}, timeout=timeout)
        pages = data.get("query", {}).get("pages", {})
        for pageid, page in pages.items():
            if pageid == "-1" or "missing" in page:
                continue
            return page.get("pageprops", {}).get("wikibase_item")
        return None

    def fetch_wikidata_description(self, qid: str, language: str = "en", timeout: float = _DEFAULT_TIMEOUT) -> str | None:
        """The short one-line description Wikidata shows under an item's
        label (e.g. "German-born theoretical physicist") -- call this on a
        client constructed with base_url=WIKIDATA_API, not the default
        en.wikipedia one, since this hits a different wiki's action API.
        """
        data = self.query(
            {"action": "wbgetentities", "ids": qid, "props": "descriptions", "languages": language},
            timeout=timeout,
        )
        entity = data.get("entities", {}).get(qid, {})
        return entity.get("descriptions", {}).get(language, {}).get("value")

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

    def redirects_to(self, pageid: int, title: str, timeout: float = _DEFAULT_TIMEOUT) -> set[str]:
        """Titles (namespace 0) of every redirect page that points at
        `pageid`. `title` is accepted only for signature parity with
        WikiReplicaClient.redirects_to (its SQL looks redirects up by
        target title, not pageid) -- unused here.

        Used by lib/link_cache.py to keep a redirect *to the answer itself*
        out of the same-shape neighbor cache: titles_to_pageids resolves a
        redirect page to its own pageid, not its target's (see that
        method's docstring), so without this exclusion such a redirect gets
        cached as a distinct degree-1 "wrong but real" neighbor instead of
        the correct guess it actually is. Leaving it out of the cache lets
        it fall through to hint_search.verify_real_article's live
        redirect-following instead, which already resolves it correctly.
        """
        out: set[str] = set()
        for page in self.query_all(
            {"pageids": pageid, "prop": "redirects", "rdnamespace": 0, "rdlimit": "max"},
            timeout=timeout,
        ):
            for entry in page.get("pages", {}).values():
                for r in entry.get("redirects", []):
                    out.add(r["title"])
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

        `srprop: redirecttitle` asks for which of a hit's incoming redirects
        actually matched the query, when the match came through one --
        `item["title"]`/`item["pageid"]` are always the target page's own
        identity even then, never the redirect's, so without this prop
        there's no way for a caller to tell a hit reached via redirect "X"
        apart from one reached via the target's own title (see
        hint_search.verify_real_article, which needs exactly that to accept
        a guess that spells a redirect rather than the canonical title).
        """
        return self.query(
            {
                "list": "search",
                "srsearch": query,
                "srnamespace": 0,
                "srlimit": limit,
                "srprop": "redirecttitle",
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
