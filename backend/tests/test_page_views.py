from datetime import date
from unittest.mock import MagicMock, patch

import requests

from backend.app.lib.geolocation import UNKNOWN_COUNTRY, resolve_country
from backend.app.lib.page_views import is_bot_request, record_page_view
from backend.app.models.country import Country
from backend.app.models.page_view import PageViewStat


# --- is_bot_request ----------------------------------------------------

def test_is_bot_request_matches_known_bot_markers():
    assert is_bot_request("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
    assert is_bot_request("curl/8.4.0")
    assert is_bot_request("python-requests/2.32.3")
    assert is_bot_request("Mozilla/5.0 (compatible; AhrefsBot/7.0)")


def test_is_bot_request_allows_real_browser_ua():
    assert not is_bot_request(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )


def test_is_bot_request_treats_missing_ua_as_bot():
    assert is_bot_request("")
    assert is_bot_request(None)


# --- resolve_country -----------------------------------------------------

def test_resolve_country_short_circuits_private_ips_without_network_call():
    with patch("backend.app.lib.geolocation.requests.get") as mock_get:
        assert resolve_country("127.0.0.1") == UNKNOWN_COUNTRY
        assert resolve_country("10.0.0.5") == UNKNOWN_COUNTRY
        assert resolve_country("192.168.1.1") == UNKNOWN_COUNTRY
    mock_get.assert_not_called()


def test_resolve_country_rejects_garbage_input_without_network_call():
    with patch("backend.app.lib.geolocation.requests.get") as mock_get:
        assert resolve_country("not-an-ip") == UNKNOWN_COUNTRY
        assert resolve_country("") == UNKNOWN_COUNTRY
    mock_get.assert_not_called()


def test_resolve_country_returns_code_on_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "success", "countryCode": "DE"}
    with patch("backend.app.lib.geolocation.requests.get", return_value=mock_response):
        assert resolve_country("8.8.8.8") == "DE"


def test_resolve_country_degrades_gracefully_on_network_failure():
    with patch("backend.app.lib.geolocation.requests.get", side_effect=requests.exceptions.Timeout):
        assert resolve_country("8.8.8.8") == UNKNOWN_COUNTRY


def test_resolve_country_degrades_gracefully_on_lookup_failure_status():
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "fail", "message": "reserved range"}
    with patch("backend.app.lib.geolocation.requests.get", return_value=mock_response):
        assert resolve_country("8.8.8.8") == UNKNOWN_COUNTRY


# --- record_page_view ------------------------------------------------------

def _seed_countries(db):
    db.session.add_all([Country(code="XX", name="Unknown"), Country(code="DE", name="Germany")])
    db.session.commit()


def test_record_page_view_creates_then_increments_todays_row(app, db):
    with app.app_context():
        _seed_countries(db)
        with patch("backend.app.lib.page_views.resolve_country", return_value="DE"):
            record_page_view("8.8.8.8", "Mozilla/5.0 real browser")
            record_page_view("203.0.113.6", "Mozilla/5.0 another real browser")

        rows = PageViewStat.query.filter_by(country_code="DE", view_date=date.today()).all()
        assert len(rows) == 1
        assert rows[0].view_count == 2


def test_record_page_view_skips_bot_requests_entirely(app, db):
    with app.app_context():
        _seed_countries(db)
        with patch("backend.app.lib.page_views.resolve_country") as mock_resolve:
            record_page_view("8.8.8.8", "curl/8.4.0")
        mock_resolve.assert_not_called()
        assert PageViewStat.query.count() == 0


def test_record_page_view_separates_counts_by_country(app, db):
    with app.app_context():
        _seed_countries(db)
        with patch("backend.app.lib.page_views.resolve_country", side_effect=["DE", "XX"]):
            record_page_view("8.8.8.8", "Mozilla/5.0 real browser")
            record_page_view("127.0.0.1", "Mozilla/5.0 real browser")

        assert PageViewStat.query.filter_by(country_code="DE").first().view_count == 1
        assert PageViewStat.query.filter_by(country_code="XX").first().view_count == 1
