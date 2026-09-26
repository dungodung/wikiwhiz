"""Deciding who gets a daily-puzzle reminder, and when.

Kept separate from scripts/send_push_reminders.py so the scheduling maths and
the trigger conditions are unit-testable without a database job, a push
service, or a clock that happens to be the right time of day.

The puzzle rolls over at 00:00 UTC, so a user's send time is simply that
boundary minus their chosen lead time. There's no per-user timezone stored
anywhere: the instant is the same for everyone with the same lead time, and
the frontend renders it in local time. That keeps the job's query trivial and
sidesteps DST entirely -- a user in a DST-observing zone sees their local
reminder time shift by an hour twice a year, which matches how the puzzle
reset itself already shifts for them.
"""

from datetime import datetime, time, timedelta, timezone

# Bounds on the lead time. 0 would mean "at the moment it's already too
# late", and 24 would mean "the instant the puzzle opened", neither of which
# is a useful reminder -- so the usable window is strictly inside the day.
MIN_HOURS_BEFORE_RESET = 1
MAX_HOURS_BEFORE_RESET = 23
DEFAULT_HOURS_BEFORE_RESET = 3

TRIGGERS = ("incomplete", "untouched")
DEFAULT_TRIGGER = "incomplete"


def clamp_hours(value) -> int | None:
    """Coerce user input to a valid lead time, or None if it isn't one.
    Returns None rather than clamping silently so the API can reject a bad
    value instead of storing a surprising one.
    """
    try:
        hours = int(value)
    except (TypeError, ValueError):
        return None
    if not MIN_HOURS_BEFORE_RESET <= hours <= MAX_HOURS_BEFORE_RESET:
        return None
    return hours


def next_reset_after(now: datetime) -> datetime:
    """The next 00:00 UTC strictly after `now` -- i.e. when the puzzle the
    user is currently able to play will be replaced.
    """
    return datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=timezone.utc)


def send_time_for(now: datetime, hours_before: int) -> datetime:
    """The UTC instant a reminder with this lead time should fire, for the
    puzzle currently in play.
    """
    return next_reset_after(now) - timedelta(hours=hours_before)


def is_due(user, now: datetime) -> bool:
    """Whether this user should be sent a reminder right now.

    The job runs hourly, so this has to be edge-triggered rather than
    level-triggered: once the send time has passed, every subsequent run
    that day would otherwise re-notify. last_notified_for_date is what makes
    it fire once -- it records the puzzle date a user was last reminded
    about, not the wall-clock date the send happened (the two are the same
    here only because the send window sits inside the puzzle's own UTC day).
    """
    if not user.notify_enabled:
        return False
    hours = clamp_hours(user.notify_hours_before_reset)
    if hours is None:
        return False
    if user.last_notified_for_date == now.date():
        return False
    return now >= send_time_for(now, hours)


def should_notify_for_session(trigger: str, session_row) -> bool:
    """Given the user's today session (or None if they never started),
    whether their chosen trigger says to nudge them.

    "untouched" is a strict subset of "incomplete": loading the page doesn't
    create a session row (game/service.py::get_session is read-only), so a
    missing row genuinely means they haven't guessed or passed at all.
    """
    if session_row is None:
        return True  # never started -- satisfies both triggers
    if trigger == "untouched":
        return False  # they've engaged; "untouched" only nags before that
    return session_row.status == "in_progress"
