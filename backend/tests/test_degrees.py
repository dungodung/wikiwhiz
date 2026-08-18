from types import SimpleNamespace
from unittest.mock import MagicMock

import requests

from backend.app.lib.degrees import compute_degrees


def test_network_failure_degrades_to_capped_not_500(app):
    """Regression test: a transient MediaWiki API failure (e.g. HTTP 429)
    during the live BFS must not raise out of compute_degrees -- the guess
    endpoint has to be able to keep responding with a degraded result.
    """
    with app.app_context():
        article = SimpleNamespace(id=1, wiki_pageid=100)
        client = MagicMock()
        client.links_batch.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")

        result = compute_degrees(
            client, article, guess_pageid=999, depth_cap=6, node_cap=100, timeout_sec=1
        )

        assert result.degrees is None
        assert result.capped is True
