from unittest.mock import MagicMock, patch

from backend.app.lib.wiki_replica import WikiReplicaClient, _from_dbkey, _to_dbkey, get_client


def _mock_client_with_rows(rows):
    """A WikiReplicaClient wrapping a fake connection whose cursor's
    fetchall() returns `rows` for every query, recording the executed SQL
    and params on the cursor mock for assertions.
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return WikiReplicaClient(conn), cursor


def test_to_dbkey_and_from_dbkey_round_trip():
    assert _to_dbkey("Albert Einstein") == "Albert_Einstein"
    assert _from_dbkey("Albert_Einstein") == "Albert Einstein"
    # A title with a real underscore-sensitive character (a hyphen) must
    # survive the round trip untouched -- only spaces convert.
    assert _from_dbkey(_to_dbkey("Jean-Paul Sartre")) == "Jean-Paul Sartre"


def test_links_batch_returns_outgoing_links_and_converts_dbkeys():
    client, cursor = _mock_client_with_rows(
        [{"from_pageid": 736, "to_title": "George_H._W._Bush"}, {"from_pageid": 736, "to_title": "Physics"}]
    )

    result = client.links_batch([736])

    assert result == {736: {"George H. W. Bush", "Physics"}}
    sql, params = cursor.execute.call_args.args
    assert "%s" in sql
    assert params == [736]


def test_links_batch_includes_pageids_with_no_links():
    client, cursor = _mock_client_with_rows([])

    result = client.links_batch([736, 999])

    assert result == {736: set(), 999: set()}


def test_linkshere_batch_returns_incoming_links():
    client, cursor = _mock_client_with_rows(
        [{"target_pageid": 736, "from_title": "Theory_of_relativity"}]
    )

    result = client.linkshere_batch([736])

    assert result == {736: {"Theory of relativity"}}


def test_titles_to_pageids_converts_to_dbkey_for_query_and_back_for_result():
    client, cursor = _mock_client_with_rows([{"page_id": 736, "page_title": "Albert_Einstein"}])

    result = client.titles_to_pageids(["Albert Einstein"])

    assert result == {"Albert Einstein": 736}
    sql, params = cursor.execute.call_args.args
    assert params == ["Albert_Einstein"]


def test_titles_to_pageids_omits_missing_titles():
    client, cursor = _mock_client_with_rows([])

    result = client.titles_to_pageids(["Nonexistent Page"])

    assert result == {}


def test_pageids_to_titles_converts_dbkey_back_to_spaces():
    client, cursor = _mock_client_with_rows([{"page_id": 736, "page_title": "Albert_Einstein"}])

    result = client.pageids_to_titles([736])

    assert result == {736: "Albert Einstein"}


def test_queries_are_parameterized_not_string_interpolated():
    """A title/pageid flowing into a WHERE clause must never be interpolated
    directly into the SQL string -- regression guard against SQL injection.
    """
    client, cursor = _mock_client_with_rows([])

    client.titles_to_pageids(["Robert'); DROP TABLE page;--"])

    sql, params = cursor.execute.call_args.args
    assert "DROP TABLE" not in sql
    assert params == ["Robert');_DROP_TABLE_page;--"]


def test_get_client_returns_none_when_cnf_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_REPLICA_CNF_PATH", str(tmp_path / "does-not-exist.cnf"))

    assert get_client() is None


def test_get_client_returns_none_on_malformed_cnf(tmp_path, monkeypatch):
    cnf = tmp_path / "replica.my.cnf"
    cnf.write_text("not valid ini [[[")
    monkeypatch.setenv("WIKI_REPLICA_CNF_PATH", str(cnf))

    assert get_client() is None


def test_get_client_returns_none_when_connection_raises(tmp_path, monkeypatch):
    cnf = tmp_path / "replica.my.cnf"
    cnf.write_text("[client]\nuser = toolsuser\npassword = secret\n")
    monkeypatch.setenv("WIKI_REPLICA_CNF_PATH", str(cnf))

    with patch("backend.app.lib.wiki_replica.pymysql.connections.Connection", side_effect=OSError("no route to host")):
        assert get_client() is None


def test_get_client_returns_working_client_on_success(tmp_path, monkeypatch):
    cnf = tmp_path / "replica.my.cnf"
    cnf.write_text("[client]\nuser = toolsuser\npassword = secret\n")
    monkeypatch.setenv("WIKI_REPLICA_CNF_PATH", str(cnf))

    fake_connection = MagicMock()
    with patch("backend.app.lib.wiki_replica.pymysql.connections.Connection", return_value=fake_connection) as mock_connect:
        client = get_client()

    assert isinstance(client, WikiReplicaClient)
    _, kwargs = mock_connect.call_args
    assert kwargs["host"] == "enwiki.analytics.db.svc.wikimedia.cloud"
    assert kwargs["database"] == "enwiki_p"
    assert kwargs["user"] == "toolsuser"
    assert kwargs["password"] == "secret"
