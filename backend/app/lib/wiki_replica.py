"""Read-only client for Wikimedia's Wiki Replicas (enwiki_p, on
*.analytics.db.svc.wikimedia.cloud) -- the primary source for the
degrees-of-Wikipedia link graph on Toolforge, dramatically cheaper than the
paginated MediaWiki Action API this module's sibling mediawiki_api.py talks
to (a single indexed JOIN vs. potentially hundreds of sequential HTTP calls
for a hub-like article). See docs/deployment-toolforge.md and
https://wikitech.wikimedia.org/wiki/Help:Toolforge/Database --
~/replica.my.cnf is auto-provisioned per-tool on Toolforge (the same file
this project's own prod DB_USER/DB_PASSWORD are sourced from, per that doc)
and simply doesn't exist on a dev machine or reach the *.svc.wikimedia.cloud
network -- which is what makes get_client() a correct, zero-config "am I on
Toolforge" signal without any separate on/off flag.

Implements the same links_batch/linkshere_batch/titles_to_pageids/
pageids_to_titles shape as mediawiki_api.MediaWikiClient (duck-typed --
this codebase doesn't use typing.Protocol/ABCs anywhere, so the contract is
documented here rather than formalized) so backend/app/lib/degrees.py and
scripts/precompute_link_cache.py can use either client interchangeably.

No redirect resolution here, matching MediaWikiClient's own
titles_to_pageids/pageids_to_titles semantics exactly (a redirect page
resolves to its own pageid, not its target's) -- this is a pure backend
swap, not a behavior change in what counts as a graph edge.
"""

import configparser
import logging
import os
import pathlib

import pymysql
import pymysql.cursors

logger = logging.getLogger(__name__)

WIKI_DB = "enwiki"  # single-wiki tool; hardcoded rather than threading a
                     # param through every call site for a value that never
                     # varies for this project.

_DEFAULT_CNF_PATH = pathlib.Path.home() / "replica.my.cnf"
_DEFAULT_CONNECT_TIMEOUT_SEC = 3.0
_QUERY_CHUNK_SIZE = 500  # SQL IN-lists tolerate far more than the API's
                         # 50-per-call limit -- this is an independent
                         # implementation detail, not a shared contract with
                         # MediaWikiClient's own chunking.


def _to_dbkey(title: str) -> str:
    return title.replace(" ", "_")


def _from_dbkey(title: str) -> str:
    return title.replace("_", " ")


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


class WikiReplicaClient:
    def __init__(self, connection: "pymysql.connections.Connection"):
        self._conn = connection

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            logger.debug("Error closing Wiki Replica connection", exc_info=True)

    def links_batch(
        self, pageids: list[int], timeout: float = 0, max_continuation_pages: int | None = None
    ) -> dict[int, set[str]]:
        """Outgoing links (namespace 0). A target need not be a real,
        existing page -- pagelinks rows are written from wikitext
        regardless of whether the target exists (a "red link"), matching
        MediaWikiClient.links_batch's own semantics. timeout/
        max_continuation_pages are accepted only for call-site
        compatibility with MediaWikiClient's signature; unused here, since
        a single SQL query has no pagination concept.
        """
        out: dict[int, set[str]] = {pid: set() for pid in pageids}
        for chunk in _chunks(pageids, _QUERY_CHUNK_SIZE):
            placeholders = ",".join(["%s"] * len(chunk))
            sql = f"""
                SELECT pl.pl_from AS from_pageid, lt.lt_title AS to_title
                FROM pagelinks pl
                JOIN linktarget lt ON lt.lt_id = pl.pl_target_id
                WHERE pl.pl_from IN ({placeholders})
                  AND pl.pl_from_namespace = 0
                  AND lt.lt_namespace = 0
            """
            with self._conn.cursor() as cur:
                cur.execute(sql, chunk)
                for row in cur.fetchall():
                    out.setdefault(row["from_pageid"], set()).add(_from_dbkey(row["to_title"]))
        return out

    def linkshere_batch(
        self, pageids: list[int], timeout: float = 0, max_continuation_pages: int | None = None
    ) -> dict[int, set[str]]:
        """Incoming links (namespace 0). Joined through `page` twice: once
        to map each target pageid to its own (namespace, title) for the
        linktarget join, once to map each linking pl_from id back to a
        title -- this second join is what guarantees every title returned
        here belongs to a real, existing page, matching linkshere's API
        semantics (unlike outgoing links, which can point at red links).
        """
        out: dict[int, set[str]] = {pid: set() for pid in pageids}
        for chunk in _chunks(pageids, _QUERY_CHUNK_SIZE):
            placeholders = ",".join(["%s"] * len(chunk))
            sql = f"""
                SELECT p_target.page_id AS target_pageid, p_from.page_title AS from_title
                FROM page p_target
                JOIN linktarget lt
                  ON lt.lt_namespace = p_target.page_namespace
                 AND lt.lt_title = p_target.page_title
                JOIN pagelinks pl ON pl.pl_target_id = lt.lt_id AND pl.pl_from_namespace = 0
                JOIN page p_from ON p_from.page_id = pl.pl_from
                WHERE p_target.page_id IN ({placeholders})
                  AND p_target.page_namespace = 0
            """
            with self._conn.cursor() as cur:
                cur.execute(sql, chunk)
                for row in cur.fetchall():
                    out.setdefault(row["target_pageid"], set()).add(_from_dbkey(row["from_title"]))
        return out

    def titles_to_pageids(self, titles: list[str], timeout: float = 0) -> dict[str, int]:
        """Batch title -> pageid. Missing titles are simply absent from the
        result. Keys the result by the *original* (space-form) title passed
        in, not the dbkey form used in the WHERE clause.
        """
        result: dict[str, int] = {}
        dbkey_to_orig = {_to_dbkey(t): t for t in titles}
        for chunk in _chunks(list(dbkey_to_orig.keys()), _QUERY_CHUNK_SIZE):
            placeholders = ",".join(["%s"] * len(chunk))
            sql = f"""
                SELECT page_id, page_title
                FROM page
                WHERE page_namespace = 0 AND page_title IN ({placeholders})
            """
            with self._conn.cursor() as cur:
                cur.execute(sql, chunk)
                for row in cur.fetchall():
                    orig = dbkey_to_orig.get(row["page_title"], _from_dbkey(row["page_title"]))
                    result[orig] = row["page_id"]
        return result

    def pageids_to_titles(self, pageids: list[int], timeout: float = 0) -> dict[int, str]:
        result: dict[int, str] = {}
        for chunk in _chunks(pageids, _QUERY_CHUNK_SIZE):
            placeholders = ",".join(["%s"] * len(chunk))
            sql = f"""
                SELECT page_id, page_title
                FROM page
                WHERE page_namespace = 0 AND page_id IN ({placeholders})
            """
            with self._conn.cursor() as cur:
                cur.execute(sql, chunk)
                for row in cur.fetchall():
                    result[row["page_id"]] = _from_dbkey(row["page_title"])
        return result


def get_client() -> WikiReplicaClient | None:
    """Never raises. Returns None on ANY failure -- missing cnf file, bad
    INI, unreachable host, auth failure, connect timeout -- so callers treat
    "no replica" and "replica down" identically and fall back to the live
    MediaWiki API without special-casing either. Callers should call this
    once per precompute run / once per guess-time BFS (not per network round
    trip within one), and close() the returned client when done, so a down
    replica costs at most one short connect-timeout rather than repeatedly
    paying it mid-traversal.
    """
    cnf_path = pathlib.Path(os.environ.get("WIKI_REPLICA_CNF_PATH") or str(_DEFAULT_CNF_PATH))
    try:
        if not cnf_path.exists():
            return None
        config = configparser.ConfigParser()
        config.read_string(cnf_path.read_text())
        user = config.get("client", "user")
        password = config.get("client", "password")
        host = os.environ.get("WIKI_REPLICA_HOST") or f"{WIKI_DB}.analytics.db.svc.wikimedia.cloud"
        database = os.environ.get("WIKI_REPLICA_DB") or f"{WIKI_DB}_p"
        timeout = float(os.environ.get("WIKI_REPLICA_CONNECT_TIMEOUT_SEC", str(_DEFAULT_CONNECT_TIMEOUT_SEC)))
        connection = pymysql.connections.Connection(
            host=host,
            database=database,
            user=user,
            password=password,
            connect_timeout=timeout,
            read_timeout=timeout * 4,  # a query budget, not the connect probe
            cursorclass=pymysql.cursors.DictCursor,
        )
        return WikiReplicaClient(connection)
    except Exception:
        logger.info("Wiki Replica unavailable, falling back to the MediaWiki API", exc_info=True)
        return None
