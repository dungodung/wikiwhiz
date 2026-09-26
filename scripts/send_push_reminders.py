#!/usr/bin/env python3
"""Hourly job: push a reminder to players who haven't finished today's puzzle.

Usage: send_push_reminders.py [--dry-run]

Intended to run once an hour via `toolforge jobs schedule` ("0 * * * *" --
see docs/deployment-toolforge.md). Each user picks a lead time (1-23 hours
before the 00:00 UTC rollover) and a trigger; this walks everyone with
reminders on, works out who is due right now, checks their trigger against
today's session, and fans a Web Push out to each device they've registered.

Running hourly rather than at one fixed time is what lets every lead time
work from a single job: the decision of "is this user due" is per-user
arithmetic (see backend/app/lib/reminders.py), not a property of when the
job fires. The cost is that a reminder lands at the top of the hour rather
than to the minute, which is well within the tolerance of a "you haven't
played yet" nudge.

Safe to run repeatedly: users.last_notified_for_date makes each user's
reminder fire at most once per puzzle date.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from _db import session_scope

from backend.app.lib import push as push_lib
from backend.app.lib.reminders import is_due, should_notify_for_session
from backend.app.models.daily_challenge import DailyChallenge
from backend.app.models.session import GameSession
from backend.app.models.user import User

logger = logging.getLogger("send_push_reminders")


def _config() -> dict:
    return {
        "VAPID_PUBLIC_KEY": os.environ.get("VAPID_PUBLIC_KEY", ""),
        "VAPID_PRIVATE_KEY": os.environ.get("VAPID_PRIVATE_KEY", ""),
        "VAPID_SUBJECT": os.environ.get("VAPID_SUBJECT", "mailto:wikiwhiz@toolforge.org"),
    }


def _hours_left_phrase(now: datetime) -> str:
    """Human phrasing for how long is left, derived from the actual instant
    rather than the user's configured lead time -- the job fires on the hour,
    so those can differ by up to an hour and the message should match
    reality, not the setting.
    """
    from backend.app.lib.reminders import next_reset_after

    minutes = int((next_reset_after(now) - now).total_seconds() // 60)
    hours = max(1, round(minutes / 60))
    return "in about an hour" if hours == 1 else f"in about {hours} hours"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report who would be notified without sending or recording anything",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = _config()
    if not push_lib.is_configured(config) and not args.dry_run:
        logger.warning("VAPID keys not configured; nothing to do")
        return 0

    now = datetime.now(timezone.utc)
    today = now.date()
    considered = due = notified = 0

    with session_scope() as session:
        challenge = (
            session.query(DailyChallenge).filter_by(challenge_date=today).first()
        )
        if challenge is None:
            logger.warning("no puzzle scheduled for %s; skipping reminders", today)
            return 0

        users = session.query(User).filter_by(notify_enabled=True).all()
        for user in users:
            considered += 1
            if not is_due(user, now):
                continue
            if not user.push_subscriptions:
                # Enabled but every device has since been pruned -- flip the
                # flag off so they stop being reconsidered every hour.
                logger.info("user %s has no live subscriptions; disabling", user.id)
                if not args.dry_run:
                    user.notify_enabled = False
                continue

            game_session = (
                session.query(GameSession)
                .filter_by(user_id=user.id, daily_challenge_id=challenge.id)
                .first()
            )
            if not should_notify_for_session(user.notify_trigger, game_session):
                # Nothing to nag about, but record the date anyway so the
                # remaining runs today skip them cheaply.
                if not args.dry_run:
                    user.last_notified_for_date = today
                continue

            due += 1
            if args.dry_run:
                logger.info(
                    "would notify user %s (%s), trigger=%s, devices=%d",
                    user.id,
                    user.wikimedia_username,
                    user.notify_trigger,
                    len(user.push_subscriptions),
                )
                continue

            delivered = push_lib.send_to_user(
                session,
                user,
                {
                    "title": "Today's WikiWhiz is still waiting",
                    "body": f"The puzzle changes {_hours_left_phrase(now)}.",
                    "url": "/",
                    # A stable tag means a second notification replaces the
                    # first rather than stacking, so a user who was offline
                    # doesn't wake to a pile of identical reminders.
                    "tag": "wikiwhiz-daily-reminder",
                },
                config,
            )
            if delivered:
                notified += 1
                user.last_notified_for_date = today
            else:
                # Leave last_notified_for_date alone so a transient failure
                # gets another attempt on the next hourly run, while there's
                # still time left before the rollover.
                logger.warning("no devices accepted the reminder for user %s", user.id)

    logger.info(
        "%s: considered=%d due=%d notified=%d",
        "dry run" if args.dry_run else "done",
        considered,
        due,
        notified,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
