import uuid

from flask import Blueprint, current_app, jsonify, request, session

from ...lib.mediawiki_api import MediaWikiClient
from . import service

game_bp = Blueprint("game", __name__)


def _get_identity() -> tuple[int | None, str | None, str | None]:
    """Returns (user_id, anon_token, new_anon_cookie_value_if_any)."""
    user_id = session.get("user_id")
    if user_id:
        return user_id, None, None

    anon_token = request.cookies.get(current_app.config["ANON_COOKIE_NAME"])
    new_cookie_value = None
    if not anon_token:
        anon_token = str(uuid.uuid4())
        new_cookie_value = anon_token
    return None, anon_token, new_cookie_value


def _set_anon_cookie(response, value: str):
    response.set_cookie(
        current_app.config["ANON_COOKIE_NAME"],
        value,
        max_age=current_app.config["ANON_COOKIE_MAX_AGE_DAYS"] * 24 * 3600,
        httponly=True,
        samesite="Lax",
    )
    return response


def _mediawiki_client() -> MediaWikiClient:
    return MediaWikiClient(current_app.config["WIKIWHIZ_USER_AGENT"])


def _degrees_config() -> dict:
    return {
        "depth_cap": current_app.config["DEGREES_LIVE_BFS_DEPTH_CAP"],
        "node_cap": current_app.config["DEGREES_LIVE_BFS_NODE_CAP"],
        "timeout_sec": current_app.config["DEGREES_LIVE_BFS_TIMEOUT_SEC"],
    }


@game_bp.get("/today")
def today():
    daily_challenge = service.get_todays_challenge()
    if daily_challenge is None:
        return jsonify({"error": "no_challenge_scheduled"}), 503

    user_id, anon_token, new_cookie_value = _get_identity()
    session_row = service.get_or_create_session(daily_challenge, user_id, anon_token)
    state = service.serialize_state(session_row, daily_challenge, daily_challenge.article)

    response = jsonify(state)
    if new_cookie_value:
        _set_anon_cookie(response, new_cookie_value)
    return response


@game_bp.post("/guess")
def guess():
    daily_challenge = service.get_todays_challenge()
    if daily_challenge is None:
        return jsonify({"error": "no_challenge_scheduled"}), 503

    user_id, anon_token, new_cookie_value = _get_identity()
    session_row = service.get_or_create_session(daily_challenge, user_id, anon_token)

    payload = request.get_json(silent=True) or {}
    guess_text = payload.get("guess_text", "")

    try:
        service.process_guess(
            session_row,
            daily_challenge,
            daily_challenge.article,
            guess_text,
            _mediawiki_client(),
            _degrees_config(),
        )
    except service.GameError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    state = service.serialize_state(session_row, daily_challenge, daily_challenge.article)
    response = jsonify(state)
    if new_cookie_value:
        _set_anon_cookie(response, new_cookie_value)
    return response
