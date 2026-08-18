#!/usr/bin/env python3
"""Daily cron check: alert the maintainer when the content pool is running low.

Usage: check_pool_level.py

Intended to run once a day (e.g. via `toolforge jobs schedule`, "10 0 * * *",
just after the UTC midnight rollover -- see docs/deployment-toolforge.md).
Counts daily_challenges with challenge_date >= today; if that count drops to
LOW_POOL_THRESHOLD or below and no alert is currently open, emails the
maintainer once and marks the alert 'active'. If the count recovers above the
threshold, silently resets 'active' to false so a future dip re-alerts.
"""

import os
import sys
from datetime import date, datetime, timezone

from _db import session_scope

from backend.app.lib.notifications import send_low_pool_alert
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.pool_alert import PoolAlertState


def main() -> int:
    threshold = int(os.environ.get("LOW_POOL_THRESHOLD", "3"))
    notify_config = {
        "MAINTAINER_EMAIL": os.environ.get("MAINTAINER_EMAIL", ""),
        "MAIL_FROM": os.environ.get("MAIL_FROM", "wikiwhiz@toolforge.org"),
        "SMTP_HOST": os.environ.get("SMTP_HOST", "localhost"),
        "SMTP_PORT": int(os.environ.get("SMTP_PORT", "25")),
        "SMTP_DEBUG_LOG_ONLY": os.environ.get("SMTP_DEBUG_LOG_ONLY", "0") == "1",
    }

    with session_scope() as session:
        today = date.today()
        remaining = session.query(DailyChallenge).filter(
            DailyChallenge.challenge_date >= today
        ).count()

        state = session.get(PoolAlertState, 1)
        if state is None:
            state = PoolAlertState(id=1, low_pool_alert_active=False)
            session.add(state)

        state.last_remaining_count = remaining
        state.last_checked_at = datetime.now(timezone.utc)

        if remaining <= threshold and not state.low_pool_alert_active:
            send_low_pool_alert(remaining, threshold, notify_config)
            state.low_pool_alert_active = True
            state.last_alert_sent_at = datetime.now(timezone.utc)
            print(f"ALERTED: remaining={remaining} threshold={threshold}")
        elif remaining > threshold and state.low_pool_alert_active:
            state.low_pool_alert_active = False
            print(f"RESET: remaining={remaining} threshold={threshold}")
        else:
            print(f"OK: remaining={remaining} threshold={threshold} alert_active={state.low_pool_alert_active}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
