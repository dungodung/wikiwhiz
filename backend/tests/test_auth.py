import pytest

from backend.app.models.user import User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


@pytest.fixture()
def user(db):
    u = User(wikimedia_sub="sub-1", wikimedia_username="Alice")
    db.session.add(u)
    db.session.commit()
    return u


def test_me_reports_unauthenticated_without_a_session(client, db):
    resp = client.get("/api/auth/me")
    assert resp.get_json() == {"authenticated": False}


def test_me_includes_hint_mode_preference_default(client, db, user):
    _login(client, user)
    resp = client.get("/api/auth/me")
    data = resp.get_json()
    assert data["authenticated"] is True
    assert data["hint_mode_preference"] is False


def test_update_hint_mode_requires_auth(client, db):
    resp = client.patch("/api/auth/hint-mode", json={"enabled": True})
    assert resp.status_code == 401


def test_update_hint_mode_persists_and_reflects_in_me(client, db, user):
    _login(client, user)

    resp = client.patch("/api/auth/hint-mode", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.get_json()["hint_mode_preference"] is True

    resp = client.get("/api/auth/me")
    assert resp.get_json()["hint_mode_preference"] is True

    resp = client.patch("/api/auth/hint-mode", json={"enabled": False})
    assert resp.get_json()["hint_mode_preference"] is False
