"""Verifies the Flask catch-all route actually serves the prebuilt frontend
(backend/app/static/), which is the mechanism the whole Toolforge Build
Service deployment strategy depends on (see docs/deployment-toolforge.md).
Skipped if the frontend hasn't been built yet (fresh checkout, no npm run).
"""

import os

import pytest


def _static_dir():
    return os.path.join(os.path.dirname(__file__), "..", "app", "static")


pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(_static_dir(), "index.html")),
    reason="frontend not built yet -- run scripts/build_frontend.sh first",
)


def test_root_serves_index_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_unknown_client_route_falls_back_to_index_html(client):
    resp = client.get("/stats")
    assert resp.status_code == 200
    assert b"<div id=\"root\">" in resp.data


def test_static_asset_is_served_directly(client):
    resp = client.get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"
