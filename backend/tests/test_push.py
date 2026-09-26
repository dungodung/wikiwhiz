"""Push subscription / reminder settings API."""

import pytest

from backend.app.models.push import PushSubscription
from backend.app.models.user import User

# A throwaway keypair generated solely for these tests -- never used by any
# deployment, and never used to sign a real push (every test that reaches the
# send path stubs pywebpush). It exists only so is_configured() returns True.
VAPID_PUBLIC = "BOjpWaN1UJJLN3Hr_fvZ67M353aggqrS1u4hUNZtrPFlG4vzgJ5ZanIgWuEwgbtvNAEcCL1R_9y_WXkv8A_6q64"
VAPID_PRIVATE = "yjjFq7zkA-7Vp0Hyk33Vvl-A4sf1-xr6WlvB2oc4CDM"

SUB = {
    "endpoint": "https://push.example.com/endpoint/abc123",
    "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"},
}


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def configured_app(app):
    """Push is opt-in via VAPID config; most tests need it switched on."""
    app.config["VAPID_PUBLIC_KEY"] = VAPID_PUBLIC
    app.config["VAPID_PRIVATE_KEY"] = VAPID_PRIVATE
    return app


@pytest.fixture()
def user(db, client):
    user = User(wikimedia_sub="push-sub", wikimedia_username="PushPat")
    db.session.add(user)
    db.session.commit()
    return user


# --- auth ----------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/push/settings"),
        ("patch", "/api/push/settings"),
        ("post", "/api/push/subscribe"),
        ("post", "/api/push/unsubscribe"),
        ("post", "/api/push/test"),
    ],
)
def test_push_endpoints_require_login(client, db, method, path):
    resp = getattr(client, method)(path, json={})
    assert resp.status_code == 401


# --- settings ------------------------------------------------------------

def test_settings_defaults_for_a_new_user(client, configured_app, user):
    _login(client, user)
    data = client.get("/api/push/settings").get_json()
    assert data["enabled"] is False
    assert data["hours_before_reset"] == 3
    assert data["trigger"] == "incomplete"
    assert data["device_count"] == 0
    assert data["subscribed_on_this_device"] is False
    assert data["vapid_public_key"] == VAPID_PUBLIC


def test_settings_report_unsupported_without_vapid_keys(client, app, user):
    app.config["VAPID_PUBLIC_KEY"] = ""
    app.config["VAPID_PRIVATE_KEY"] = ""
    _login(client, user)
    assert client.get("/api/push/settings").get_json()["supported"] is False


def test_reset_and_send_instants_are_utc_and_differ_by_the_lead_time(client, configured_app, user):
    """The server sends instants, not formatted times -- the browser is what
    knows the player's timezone.
    """
    from datetime import datetime

    _login(client, user)
    data = client.patch("/api/push/settings", json={"hours_before_reset": 5}).get_json()
    reset = datetime.fromisoformat(data["next_reset_utc"].replace("Z", "+00:00"))
    send = datetime.fromisoformat(data["next_send_utc"].replace("Z", "+00:00"))
    assert (reset - send).total_seconds() == 5 * 3600
    assert reset.hour == 0 and reset.minute == 0  # UTC midnight rollover


def test_update_settings_persists_hours_and_trigger(client, configured_app, db, user):
    _login(client, user)
    data = client.patch(
        "/api/push/settings", json={"hours_before_reset": 6, "trigger": "untouched"}
    ).get_json()
    assert data["hours_before_reset"] == 6
    assert data["trigger"] == "untouched"
    db.session.refresh(user)
    assert user.notify_hours_before_reset == 6
    assert user.notify_trigger == "untouched"


@pytest.mark.parametrize("hours", [0, 24, -3, "nope"])
def test_update_settings_rejects_out_of_range_hours(client, configured_app, hours, user):
    _login(client, user)
    resp = client.patch("/api/push/settings", json={"hours_before_reset": hours})
    assert resp.status_code == 400


def test_update_settings_rejects_an_unknown_trigger(client, configured_app, user):
    _login(client, user)
    resp = client.patch("/api/push/settings", json={"trigger": "whenever"})
    assert resp.status_code == 400


def test_changing_settings_rearms_todays_reminder(client, configured_app, db, user):
    """Otherwise a user who already got today's nudge couldn't move the time
    earlier and see it take effect until tomorrow.
    """
    from datetime import date

    user.last_notified_for_date = date(2026, 9, 26)
    db.session.commit()
    _login(client, user)
    client.patch("/api/push/settings", json={"hours_before_reset": 8})
    db.session.refresh(user)
    assert user.last_notified_for_date is None


# --- subscribe / unsubscribe --------------------------------------------

def test_subscribe_registers_the_device_and_enables_reminders(client, configured_app, db, user):
    _login(client, user)
    data = client.post("/api/push/subscribe", json=SUB).get_json()
    assert data["enabled"] is True
    assert data["device_count"] == 1
    assert data["subscribed_on_this_device"] is True
    db.session.refresh(user)
    assert user.notify_enabled is True


def test_subscribing_twice_with_the_same_endpoint_is_idempotent(client, configured_app, db, user):
    """Browsers re-subscribe on their own (e.g. after an endpoint rotation);
    that must update the row, not pile up duplicates.
    """
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    data = client.post("/api/push/subscribe", json=SUB).get_json()
    assert data["device_count"] == 1
    assert PushSubscription.query.filter_by(endpoint=SUB["endpoint"]).count() == 1


def test_subscribe_accepts_settings_in_the_same_call(client, configured_app, user):
    _login(client, user)
    data = client.post(
        "/api/push/subscribe", json={**SUB, "hours_before_reset": 2, "trigger": "untouched"}
    ).get_json()
    assert data["hours_before_reset"] == 2
    assert data["trigger"] == "untouched"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"endpoint": "https://push.example.com/x"},  # no keys
        {"endpoint": "", "keys": {"p256dh": "a", "auth": "b"}},
        {"endpoint": "https://push.example.com/x", "keys": {"p256dh": "a"}},
    ],
)
def test_subscribe_rejects_malformed_subscriptions(client, configured_app, body, user):
    _login(client, user)
    assert client.post("/api/push/subscribe", json=body).status_code == 400


def test_subscribe_is_unavailable_without_vapid_keys(client, app, user):
    app.config["VAPID_PUBLIC_KEY"] = ""
    app.config["VAPID_PRIVATE_KEY"] = ""
    _login(client, user)
    assert client.post("/api/push/subscribe", json=SUB).status_code == 503


def test_a_reused_endpoint_moves_to_the_new_owner(client, configured_app, db, user):
    """Shared device, or a user switching accounts -- the endpoint must not
    keep delivering to whoever registered it first.
    """
    other = User(wikimedia_sub="other-sub", wikimedia_username="OtherOtto")
    db.session.add(other)
    db.session.commit()

    _login(client, other)
    client.post("/api/push/subscribe", json=SUB)
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)

    row = PushSubscription.query.filter_by(endpoint=SUB["endpoint"]).one()
    assert row.user_id == user.id


def test_unsubscribe_removes_the_device_and_disables_reminders(client, configured_app, db, user):
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    data = client.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]}).get_json()
    assert data["enabled"] is False
    assert data["device_count"] == 0
    db.session.refresh(user)
    assert user.notify_enabled is False
    assert PushSubscription.query.count() == 0


def test_unsubscribing_one_of_two_devices_keeps_reminders_on(client, configured_app, db, user):
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    second = {
        "endpoint": "https://push.example.com/endpoint/second",
        "keys": {"p256dh": "k2", "auth": "a2"},
    }
    client.post("/api/push/subscribe", json=second)

    data = client.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]}).get_json()
    assert data["enabled"] is True
    assert data["device_count"] == 1
    db.session.refresh(user)
    assert user.notify_enabled is True


def test_unsubscribe_without_an_endpoint_removes_every_device(client, configured_app, db, user):
    """The "turn it off everywhere" path, for a user who no longer has the
    old device to unsubscribe from.
    """
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://push.example.com/e2", "keys": {"p256dh": "k", "auth": "a"}},
    )
    data = client.post("/api/push/unsubscribe", json={}).get_json()
    assert data["device_count"] == 0
    assert data["enabled"] is False


def test_unsubscribe_is_harmless_when_nothing_is_registered(client, configured_app, user):
    _login(client, user)
    resp = client.post("/api/push/unsubscribe", json={"endpoint": SUB["endpoint"]})
    assert resp.status_code == 200
    assert resp.get_json()["device_count"] == 0


# --- test send -----------------------------------------------------------

def test_test_send_requires_a_subscription(client, configured_app, user):
    _login(client, user)
    resp = client.post("/api/push/test")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "no_subscriptions"


def test_test_send_reports_failure_when_nothing_is_delivered(client, configured_app, user, monkeypatch):
    """The endpoint is fake, so pywebpush can't deliver -- the UI needs a
    non-200 to tell the user rather than claiming success.
    """
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)

    from backend.app.lib import push as push_lib

    monkeypatch.setattr(push_lib, "send_to_user", lambda *a, **kw: 0)
    resp = client.post("/api/push/test")
    assert resp.status_code == 502


def test_test_send_reports_delivery_count(client, configured_app, user, monkeypatch):
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)

    from backend.app.lib import push as push_lib

    monkeypatch.setattr(push_lib, "send_to_user", lambda *a, **kw: 1)
    resp = client.post("/api/push/test")
    assert resp.status_code == 200
    assert resp.get_json()["delivered"] == 1


# --- dead-endpoint pruning ----------------------------------------------

class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def _raise_webpush(status):
    from pywebpush import WebPushException

    def _inner(*args, **kwargs):
        raise WebPushException("boom", response=_FakeResponse(status))

    return _inner


@pytest.mark.parametrize("status", [404, 410])
def test_a_permanently_gone_endpoint_is_deleted(client, configured_app, db, user, monkeypatch, status):
    """Dead endpoints never recover, so retrying them forever would grow an
    unbounded pile of corpses and misreport the user's device count.
    """
    import pywebpush

    from backend.app.lib import push as push_lib

    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    monkeypatch.setattr(pywebpush, "webpush", _raise_webpush(status))

    delivered = push_lib.send_to_user(db.session, user, {"title": "x"}, configured_app.config)
    db.session.commit()

    assert delivered == 0
    assert PushSubscription.query.count() == 0


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_transient_failure_keeps_the_subscription(client, configured_app, db, user, monkeypatch, status):
    """A push service outage must not discard working subscriptions."""
    import pywebpush

    from backend.app.lib import push as push_lib

    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)
    monkeypatch.setattr(pywebpush, "webpush", _raise_webpush(status))

    delivered = push_lib.send_to_user(db.session, user, {"title": "x"}, configured_app.config)
    db.session.commit()

    assert delivered == 0
    assert PushSubscription.query.count() == 1


def test_send_is_a_no_op_without_vapid_keys(client, app, db, user):
    app.config["VAPID_PUBLIC_KEY"] = VAPID_PUBLIC
    app.config["VAPID_PRIVATE_KEY"] = VAPID_PRIVATE
    _login(client, user)
    client.post("/api/push/subscribe", json=SUB)

    from backend.app.lib import push as push_lib

    unconfigured = {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": ""}
    assert push_lib.send_to_user(db.session, user, {"title": "x"}, unconfigured) == 0
    assert PushSubscription.query.count() == 1  # not pruned -- it wasn't tried
