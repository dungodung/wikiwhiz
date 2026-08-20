"""Anonymous, aggregated page-view tracking: increments a per-(country,
date) counter whenever the frontend's index.html is served to what looks
like a real visitor. See lib/geolocation.py for the IP -> country lookup
(the IP itself is never stored) and models/page_view.py for why this is
aggregated counts rather than a per-visit log.

Bot filtering is a plain User-Agent substring denylist -- inherently
best-effort (a bot can always spoof a browser UA), but that's an acceptable
trade for "don't bother counting obvious bots" rather than a security
control.
"""

import logging
import threading
from datetime import date

from flask import current_app

from ..extensions import db
from ..models.page_view import PageViewStat
from .geolocation import resolve_country

logger = logging.getLogger(__name__)

_BOT_UA_MARKERS = (
    "bot",
    "spider",
    "crawl",
    "slurp",
    "curl",
    "wget",
    "python-requests",
    "python-urllib",
    "facebookexternalhit",
    "whatsapp",
    "telegrambot",
    "monitoring",
    "uptimerobot",
    "pingdom",
    "ahrefsbot",
    "semrushbot",
    "mj12bot",
    "dotbot",
    "petalbot",
    "headlesschrome",
    "phantomjs",
    "go-http-client",
    "libwww-perl",
    "scrapy",
    "httpclient",
)


def is_bot_request(user_agent: str) -> bool:
    ua = (user_agent or "").strip().lower()
    if not ua:
        return True  # no UA at all is itself a strong script/bot signal
    return any(marker in ua for marker in _BOT_UA_MARKERS)


def record_page_view(ip: str, user_agent: str) -> None:
    """Synchronous: resolves the country and increments today's count for
    it. Called from a background thread in normal operation (see
    track_page_view_async) since it does a live HTTP call and a DB write,
    neither of which should block the page response -- exposed directly
    here too since that's what tests call, and it's a reasonable thing for
    any other synchronous caller to use directly.
    """
    if is_bot_request(user_agent):
        return

    country_code = resolve_country(ip)
    today = date.today()

    stat = PageViewStat.query.filter_by(country_code=country_code, view_date=today).first()
    if stat is None:
        stat = PageViewStat(country_code=country_code, view_date=today, view_count=0)
        db.session.add(stat)
    stat.view_count += 1
    db.session.commit()


def track_page_view_async(ip: str, user_agent: str) -> None:
    """Fire-and-forget from a request handler: a page load must never wait
    on an external geolocation call. Mirrors
    game/service.py::_spawn_live_degrees_computation's pattern for the same
    reason -- a fresh app context is required since Flask-SQLAlchemy's
    session is tied to the request's context, which will be gone by the
    time this thread runs.
    """
    if is_bot_request(user_agent):
        return

    app = current_app._get_current_object()

    def worker() -> None:
        with app.app_context():
            try:
                record_page_view(ip, user_agent)
            except Exception:
                logger.exception("Page-view tracking failed")
                db.session.rollback()

    threading.Thread(target=worker, daemon=True).start()
