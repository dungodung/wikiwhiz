from datetime import date

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


# --- record_page_view ------------------------------------------------------

REAL_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 real browser"


def _seed_countries(db):
    db.session.add_all([Country(code="XX", name="Unknown"), Country(code="DE", name="Germany")])
    db.session.commit()


def test_record_page_view_creates_then_increments_todays_row(app, db):
    with app.app_context():
        _seed_countries(db)
        record_page_view("DE", REAL_UA)
        record_page_view("de", REAL_UA)  # lowercase from a sloppy client -- still counts as DE

        rows = PageViewStat.query.filter_by(country_code="DE", view_date=date.today()).all()
        assert len(rows) == 1
        assert rows[0].view_count == 2


def test_record_page_view_falls_back_to_unknown_for_invalid_code(app, db):
    with app.app_context():
        _seed_countries(db)
        record_page_view("not-a-real-code", REAL_UA)
        record_page_view("", REAL_UA)

        stat = PageViewStat.query.filter_by(country_code="XX").first()
        assert stat.view_count == 2


def test_record_page_view_skips_bot_requests_entirely(app, db):
    with app.app_context():
        _seed_countries(db)
        record_page_view("DE", "curl/8.4.0")
        assert PageViewStat.query.count() == 0


def test_record_page_view_separates_counts_by_country(app, db):
    with app.app_context():
        _seed_countries(db)
        record_page_view("DE", REAL_UA)
        record_page_view("XX", REAL_UA)

        assert PageViewStat.query.filter_by(country_code="DE").first().view_count == 1
        assert PageViewStat.query.filter_by(country_code="XX").first().view_count == 1


# --- POST /api/info/page-view ---------------------------------------------

def test_page_view_endpoint_records_a_visit(client, db):
    _seed_countries(db)
    resp = client.post(
        "/api/info/page-view",
        json={"country_code": "DE"},
        headers={"User-Agent": REAL_UA},
    )
    assert resp.status_code == 204
    assert PageViewStat.query.filter_by(country_code="DE").first().view_count == 1


def test_page_view_endpoint_never_errors_on_missing_payload(client, db):
    _seed_countries(db)
    resp = client.post("/api/info/page-view")
    assert resp.status_code == 204
    assert PageViewStat.query.filter_by(country_code="XX").first().view_count == 1
