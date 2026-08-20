"""Best-effort IP -> country resolution for anonymous page-view stats.

Deliberately never stores the visitor's IP anywhere -- resolve_country()
takes it, makes one lookup call, and returns just a country code; nothing
upstream of this module ever persists the IP itself (see lib/page_views.py).

Uses ip-api.com's free tier: no signup/API key needed, generous for this
project's traffic (45 req/min). It's HTTP-only on the free tier, which is
fine here since this call happens server-to-server (never loaded into a
browser), so there's no mixed-content concern -- only an API key would need
protecting, and there isn't one.

Fails soft everywhere: a private/loopback IP (local dev, internal health
checks), a network error, a timeout, or a malformed response all resolve to
UNKNOWN_COUNTRY rather than raising -- this must never be able to break a
page load, since it's a nice-to-have stat, not a critical path.
"""

import ipaddress
import logging

import requests

logger = logging.getLogger(__name__)

GEOLOCATION_API = "http://ip-api.com/json/{ip}"
UNKNOWN_COUNTRY = "XX"
_TIMEOUT = 3


def resolve_country(ip: str) -> str:
    try:
        addr = ipaddress.ip_address(ip)
    except (ValueError, TypeError):
        return UNKNOWN_COUNTRY

    # Local dev, Docker networks, internal health checks -- none of these
    # are geolocatable, and sending them to ip-api.com would just waste a
    # call and always come back unresolved anyway.
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        return UNKNOWN_COUNTRY

    try:
        resp = requests.get(
            GEOLOCATION_API.format(ip=ip),
            params={"fields": "status,countryCode"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        logger.warning("Geolocation lookup failed for page-view tracking", exc_info=True)
        return UNKNOWN_COUNTRY

    if data.get("status") == "success" and data.get("countryCode"):
        return data["countryCode"]
    return UNKNOWN_COUNTRY
