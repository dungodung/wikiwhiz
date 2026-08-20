from flask import Blueprint, jsonify, request

from ...lib.page_views import record_page_view

info_bp = Blueprint("info", __name__)


@info_bp.get("")
def info():
    # Static "about the game / about the author" content lives in the
    # frontend's InfoPage component; this stub exists for future dynamic
    # content (e.g. surfacing the current content-pool size).
    return jsonify({"status": "ok"})


@info_bp.post("/page-view")
def page_view():
    """Called once per real page load by the frontend (see App.jsx), after
    it resolves its own country client-side -- see lib/page_views.py's
    module docstring for why this is client- rather than server-resolved.
    Always 204: a client tracking beacon has nothing useful to do with an
    error response, and a bad/missing country_code just falls back to the
    'XX' sentinel rather than failing the request.
    """
    payload = request.get_json(silent=True) or {}
    record_page_view(payload.get("country_code", ""), request.headers.get("User-Agent", ""))
    return "", 204
