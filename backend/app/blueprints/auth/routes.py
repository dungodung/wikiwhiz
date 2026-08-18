from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, request, session

from ...extensions import db
from ...models.user import User
from . import oauth_client

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    state = oauth_client.new_state()
    session["oauth_state"] = state
    url = oauth_client.build_authorize_url(
        current_app.config["WIKIWHIZ_OAUTH_CLIENT_ID"],
        current_app.config["WIKIWHIZ_OAUTH_REDIRECT_URI"],
        state,
    )
    return redirect(url)


@auth_bp.get("/callback")
def callback():
    expected_state = session.pop("oauth_state", None)
    state = request.args.get("state")
    code = request.args.get("code")
    if not code or not state or state != expected_state:
        return jsonify({"error": "invalid_state"}), 400

    token = oauth_client.exchange_code_for_token(
        current_app.config["WIKIWHIZ_OAUTH_CLIENT_ID"],
        current_app.config["WIKIWHIZ_OAUTH_CLIENT_SECRET"],
        current_app.config["WIKIWHIZ_OAUTH_REDIRECT_URI"],
        code,
    )
    profile = oauth_client.fetch_profile(token["access_token"])

    user = User.query.filter_by(wikimedia_sub=str(profile["sub"])).first()
    if user is None:
        user = User(
            wikimedia_sub=str(profile["sub"]),
            wikimedia_username=profile["username"],
        )
        db.session.add(user)
    user.wikimedia_username = profile["username"]
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    session["user_id"] = user.id
    return redirect("/")


@auth_bp.post("/logout")
def logout():
    session.pop("user_id", None)
    return "", 204


@auth_bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False})
    user = db.session.get(User, user_id)
    if user is None:
        session.pop("user_id", None)
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "username": user.wikimedia_username})
