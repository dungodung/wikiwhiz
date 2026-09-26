"""Web Push subscription and daily-reminder settings.

Logged-in only: a reminder needs somewhere durable to hang off, and an anon
cookie can vanish at any time. Every endpoint 401s for anonymous callers,
matching auth/routes.py's theme and hint-mode handlers.

The settings themselves live on User (one set of preferences per person),
while subscriptions are per-device rows -- so a user can be subscribed on
their phone and not their laptop, and turning the feature off from either
one removes that device and stops reminders everywhere.
"""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session

from ...extensions import db
from ...lib import push as push_lib
from ...lib.reminders import (
    DEFAULT_HOURS_BEFORE_RESET,
    MAX_HOURS_BEFORE_RESET,
    MIN_HOURS_BEFORE_RESET,
    TRIGGERS,
    clamp_hours,
    send_time_for,
)
from ...models.push import PushSubscription
from ...models.user import User

push_bp = Blueprint("push", __name__)


def _current_user() -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if user is None:
        session.pop("user_id", None)
    return user


def _settings_payload(user: User, endpoint: str | None = None) -> dict:
    now = datetime.now(timezone.utc)
    hours = clamp_hours(user.notify_hours_before_reset) or DEFAULT_HOURS_BEFORE_RESET
    return {
        "supported": push_lib.is_configured(current_app.config),
        "vapid_public_key": push_lib.public_key(current_app.config),
        "enabled": user.notify_enabled,
        "hours_before_reset": hours,
        "trigger": user.notify_trigger,
        "min_hours": MIN_HOURS_BEFORE_RESET,
        "max_hours": MAX_HOURS_BEFORE_RESET,
        # Both as UTC ISO instants; the browser renders them in local time,
        # which is the whole point of sending instants rather than a
        # formatted string -- the server has no idea what zone the user is in.
        "next_reset_utc": send_time_for(now, 0).isoformat().replace("+00:00", "Z"),
        "next_send_utc": send_time_for(now, hours).isoformat().replace("+00:00", "Z"),
        "device_count": len(user.push_subscriptions),
        # Whether *this* browser is registered, so the UI can distinguish
        # "on, but not on this device" from "on here".
        "subscribed_on_this_device": bool(
            endpoint and any(s.endpoint == endpoint for s in user.push_subscriptions)
        ),
    }


@push_bp.get("/settings")
def get_settings():
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_authenticated"}), 401
    return jsonify(_settings_payload(user, request.args.get("endpoint")))


@push_bp.patch("/settings")
def update_settings():
    """Change lead time and/or trigger. Deliberately does not turn the
    feature on -- that needs a subscription, so it goes through /subscribe.
    """
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_authenticated"}), 401

    payload = request.get_json(silent=True) or {}
    if "hours_before_reset" in payload:
        hours = clamp_hours(payload["hours_before_reset"])
        if hours is None:
            return jsonify({"error": "invalid_hours"}), 400
        user.notify_hours_before_reset = hours
    if "trigger" in payload:
        if payload["trigger"] not in TRIGGERS:
            return jsonify({"error": "invalid_trigger"}), 400
        user.notify_trigger = payload["trigger"]

    # Changing settings re-arms today's reminder: without this, a user who
    # already got today's nudge couldn't move the time earlier and see the
    # effect until tomorrow.
    user.last_notified_for_date = None
    db.session.commit()
    return jsonify(_settings_payload(user, payload.get("endpoint")))


@push_bp.post("/subscribe")
def subscribe():
    """Register this browser and switch reminders on.

    Idempotent on endpoint: a browser that re-subscribes (which it may do on
    its own, e.g. after a push service rotates the endpoint) updates its
    existing row rather than creating a duplicate.
    """
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_authenticated"}), 401
    if not push_lib.is_configured(current_app.config):
        return jsonify({"error": "push_not_configured"}), 503

    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth:
        return jsonify({"error": "invalid_subscription"}), 400
    if len(endpoint) > 500:
        return jsonify({"error": "endpoint_too_long"}), 400

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing is None:
        db.session.add(
            PushSubscription(user_id=user.id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        )
    else:
        # Re-point it if the same endpoint somehow belongs to another account
        # (shared device, user switched logins) rather than leaving it
        # delivering to the wrong person.
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth

    if "hours_before_reset" in payload:
        hours = clamp_hours(payload["hours_before_reset"])
        if hours is None:
            return jsonify({"error": "invalid_hours"}), 400
        user.notify_hours_before_reset = hours
    if "trigger" in payload:
        if payload["trigger"] not in TRIGGERS:
            return jsonify({"error": "invalid_trigger"}), 400
        user.notify_trigger = payload["trigger"]

    user.notify_enabled = True
    user.last_notified_for_date = None
    db.session.commit()
    return jsonify(_settings_payload(user, endpoint))


@push_bp.post("/unsubscribe")
def unsubscribe():
    """Remove this device, and turn reminders off entirely once no device is
    left. Called both by the settings modal's off switch and when a browser
    reports its subscription has gone stale.

    With no endpoint supplied this removes *every* device -- the "turn it off
    everywhere" path, so a user who's lost access to an old phone isn't stuck
    receiving reminders on it.
    """
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_authenticated"}), 401

    payload = request.get_json(silent=True) or {}
    endpoint = (payload.get("endpoint") or "").strip()

    if endpoint:
        PushSubscription.query.filter_by(user_id=user.id, endpoint=endpoint).delete()
    else:
        PushSubscription.query.filter_by(user_id=user.id).delete()

    db.session.flush()
    if not PushSubscription.query.filter_by(user_id=user.id).count():
        user.notify_enabled = False
    db.session.commit()
    return jsonify(_settings_payload(user, endpoint or None))


@push_bp.post("/test")
def send_test():
    """Fire a notification at this user immediately, so they can confirm
    permission and delivery actually work before trusting it for tomorrow's
    puzzle -- push failures are otherwise completely silent from the UI.
    """
    user = _current_user()
    if user is None:
        return jsonify({"error": "not_authenticated"}), 401
    if not push_lib.is_configured(current_app.config):
        return jsonify({"error": "push_not_configured"}), 503
    if not user.push_subscriptions:
        return jsonify({"error": "no_subscriptions"}), 400

    delivered = push_lib.send_to_user(
        db.session,
        user,
        {
            "title": "WikiWhiz reminder test",
            "body": "Notifications are working. You'll get a nudge like this before the puzzle changes.",
            "url": "/",
            "tag": "wikiwhiz-test",
        },
        current_app.config,
    )
    db.session.commit()
    if not delivered:
        return jsonify({"error": "delivery_failed"}), 502
    return jsonify({"delivered": delivered})
