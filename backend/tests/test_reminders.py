"""Unit tests for the reminder scheduling maths and trigger conditions.

Pure functions over a fake user/session, so none of this needs a database,
a clock at a particular time of day, or a push service.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.lib.reminders import (
    MAX_HOURS_BEFORE_RESET,
    MIN_HOURS_BEFORE_RESET,
    clamp_hours,
    is_due,
    next_reset_after,
    send_time_for,
    should_notify_for_session,
)


class _FakeUser:
    def __init__(self, enabled=True, hours=3, trigger="incomplete", last_notified=None):
        self.notify_enabled = enabled
        self.notify_hours_before_reset = hours
        self.notify_trigger = trigger
        self.last_notified_for_date = last_notified


class _FakeSession:
    def __init__(self, status):
        self.status = status


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# --- scheduling maths ----------------------------------------------------

def test_next_reset_is_the_following_utc_midnight():
    assert next_reset_after(_utc(2026, 9, 26, 13, 30)) == _utc(2026, 9, 27)


def test_next_reset_from_just_after_midnight_is_a_full_day_away():
    """A user at 00:01 is playing the puzzle that expires ~24h later, not the
    one that just expired a minute ago.
    """
    assert next_reset_after(_utc(2026, 9, 26, 0, 1)) == _utc(2026, 9, 27)


def test_send_time_subtracts_the_lead_time_from_the_reset():
    assert send_time_for(_utc(2026, 9, 26, 10, 0), 3) == _utc(2026, 9, 26, 21, 0)


def test_max_lead_time_still_lands_inside_the_same_puzzle_day():
    sent = send_time_for(_utc(2026, 9, 26, 10, 0), MAX_HOURS_BEFORE_RESET)
    assert sent == _utc(2026, 9, 26, 1, 0)


# --- input validation ----------------------------------------------------

@pytest.mark.parametrize("value", [MIN_HOURS_BEFORE_RESET, 3, MAX_HOURS_BEFORE_RESET, "5"])
def test_clamp_hours_accepts_valid_values(value):
    assert clamp_hours(value) == int(value)


@pytest.mark.parametrize("value", [0, 24, -1, 100, None, "", "abc"])
def test_clamp_hours_rejects_out_of_range_and_junk(value):
    assert clamp_hours(value) is None


# --- due logic -----------------------------------------------------------

def test_not_due_before_the_send_time():
    now = _utc(2026, 9, 26, 12, 0)  # send time is 21:00
    assert is_due(_FakeUser(hours=3), now) is False


def test_due_once_the_send_time_has_passed():
    now = _utc(2026, 9, 26, 21, 30)
    assert is_due(_FakeUser(hours=3), now) is True


def test_due_exactly_at_the_send_time():
    assert is_due(_FakeUser(hours=3), _utc(2026, 9, 26, 21, 0)) is True


def test_not_due_when_disabled():
    assert is_due(_FakeUser(enabled=False, hours=3), _utc(2026, 9, 26, 23, 0)) is False


def test_not_due_twice_on_the_same_puzzle_date():
    """The job runs hourly; without the last-notified guard every run after
    the send time would re-notify.
    """
    now = _utc(2026, 9, 26, 22, 0)
    user = _FakeUser(hours=3, last_notified=date(2026, 9, 26))
    assert is_due(user, now) is False


def test_due_again_the_next_day():
    user = _FakeUser(hours=3, last_notified=date(2026, 9, 26))
    assert is_due(user, _utc(2026, 9, 27, 22, 0)) is True


def test_not_due_with_a_corrupt_lead_time():
    """Defensive: a bad stored value shouldn't make the job crash or notify
    at an arbitrary time.
    """
    assert is_due(_FakeUser(hours=0), _utc(2026, 9, 26, 23, 59)) is False


# --- trigger conditions --------------------------------------------------

def test_both_triggers_fire_when_the_player_never_started():
    assert should_notify_for_session("incomplete", None) is True
    assert should_notify_for_session("untouched", None) is True


def test_incomplete_fires_for_a_game_still_in_progress():
    assert should_notify_for_session("incomplete", _FakeSession("in_progress")) is True


def test_untouched_stays_quiet_once_the_player_has_engaged():
    assert should_notify_for_session("untouched", _FakeSession("in_progress")) is False


@pytest.mark.parametrize("status", ["won", "lost"])
def test_no_trigger_fires_for_a_finished_game(status):
    assert should_notify_for_session("incomplete", _FakeSession(status)) is False
    assert should_notify_for_session("untouched", _FakeSession(status)) is False
