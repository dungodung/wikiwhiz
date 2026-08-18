from flask import Blueprint, jsonify

info_bp = Blueprint("info", __name__)


@info_bp.get("")
def info():
    # Static "about the game / about the author" content lives in the
    # frontend's InfoPage component; this stub exists for future dynamic
    # content (e.g. surfacing the current content-pool size).
    return jsonify({"status": "ok"})
