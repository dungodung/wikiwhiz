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


class MediaWikiClient:
    def __init__(self, user_agent: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def query(self, params: dict, timeout: float = _DEFAULT_TIMEOUT) -> dict:
        params = {**params, "action": "query", "format": "json"}
        resp = self.session.get(WIKIPEDIA_API, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def query_all(self, params: dict, timeout: float = _DEFAULT_TIMEOUT):
        """Generator that follows `continue` tokens, yielding each response's
        'query' dict in turn. Caller merges whichever sub-keys it needs.
        """
        params = dict(params)
        while True:
            data = self.query(params, timeout=timeout)
            yield data.get("query", {})
            if "continue" not in data:
                return
            params.update(data["continue"])

    def resolve_title(self, title: str, timeout: float = _DEFAULT_TIMEOUT) -> dict | None:
        """Exact title lookup, following redirects. Returns {"pageid","title"} or None."""
        data = self.query({"titles": title, "redirects": 1}, timeout=timeout)
        pages = data.get("query", {}).get("pages", {})
        for pageid, page in pages.items():
            if pageid == "-1" or "missing" in page:
                continue
            return {"pageid": int(pageid), "title": page["title"]}
        return None

    def search_title(self, text: str, timeout: float = _DEFAULT_TIMEOUT) -> dict | None:
        """Best-effort free-text search, for guesses that aren't an exact title."""
        data = self.query(
            {"list": "search", "srsearch": text, "srlimit": 1}, timeout=timeout
        )
        results = data.get("query", {}).get("search", [])
        if not results:
            return None
        return self.resolve_title(results[0]["title"], timeout=timeout)

    def links_batch(self, pageids: list[int], timeout: float = _DEFAULT_TIMEOUT) -> dict[int, set[str]]:
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
            ):
                for pageid_str, page in query.get("pages", {}).items():
                    pageid = int(pageid_str)
                    for link in page.get("links", []):
                        out.setdefault(pageid, set()).add(link["title"])
        return out

    def linkshere_batch(self, pageids: list[int], timeout: float = _DEFAULT_TIMEOUT) -> dict[int, set[str]]:
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
            ):
                for pageid_str, page in query.get("pages", {}).items():
                    pageid = int(pageid_str)
                    for link in page.get("linkshere", []):
                        out.setdefault(pageid, set()).add(link["title"])
        return out


def now() -> float:
    return time.monotonic()
