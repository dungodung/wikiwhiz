"""Anonymous, aggregated page-view tracking: increments a per-(country,
date) counter for each real page load. See models/page_view.py for why
this is aggregated counts rather than a per-visit log.

Country resolution happens client-side (see frontend/src/lib/geolocation.js),
not here -- confirmed live this session that Toolforge's edge network
strips the real visitor IP before it ever reaches a tool's container
(X-Forwarded-For / X-Envoy-External-Address both showed the platform's own
internal address, never the visitor's), so server-side IP geolocation
cannot work on this deployment target at all. The browser resolves its own
country directly against a free geolocation service and POSTs just the
resulting country code to /api/info/page-view -- this module never sees or
stores an IP address, which if anything is a stronger privacy story than
the originally-planned server-side lookup would have been.

Bot filtering is a plain User-Agent substring denylist -- inherently
best-effort, but a script/bot posting directly to this endpoint (rather
than a browser that ran the client-side geolocation fetch first) is also a
much smaller share of traffic than it would have been on every page load,
since most simple bots never execute the frontend JS that triggers this
call at all.
"""

from datetime import date

from ..extensions import db
from ..models.country import Country
from ..models.page_view import PageViewStat

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


def record_page_view(country_code: str, user_agent: str) -> None:
    """country_code: whatever the client's geolocation lookup returned,
    already validated against the countries codebook -- falls back to the
    'XX' sentinel for anything not recognized (a lookup failure the client
    reported honestly, a made-up code, wrong casing, etc.) rather than
    rejecting the request outright, since this is a best-effort stat, not
    something worth failing a request over.
    """
    if is_bot_request(user_agent):
        return

    code = (country_code or "").strip().upper()
    if not db.session.get(Country, code):
        code = "XX"

    today = date.today()
    stat = PageViewStat.query.filter_by(country_code=code, view_date=today).first()
    if stat is None:
        stat = PageViewStat(country_code=code, view_date=today, view_count=0)
        db.session.add(stat)
    stat.view_count += 1
    db.session.commit()
