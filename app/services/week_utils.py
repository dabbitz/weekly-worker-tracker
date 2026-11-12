"""Shared helpers for Istanbul-based weekly planning.

The planning weeks used by the weekly plan service start on Monday, cover
seven days, and are clipped to a task's real planned start and due dates.
These helpers keep that behaviour unchanged; they only answer date
questions for the employee-facing report flow.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.database.models import WeeklyTaskPlan


TIMEZONE = ZoneInfo("Europe/Istanbul")


def istanbul_today(now: datetime | None = None) -> date:
    """Return today's date in the Europe/Istanbul time zone.

    ``now`` exists for tests. A naive datetime is interpreted as UTC,
    matching Telegram's message timestamps and the date normalizer.
    """

    if now is None:
        return datetime.now(TIMEZONE).date()

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return now.astimezone(TIMEZONE).date()


def monday_of(value: date) -> date:
    """Return the Monday of the calendar week containing ``value``."""

    return value - timedelta(days=value.weekday())


def week_contains(plan: WeeklyTaskPlan, value: date) -> bool:
    """Return whether ``value`` falls inside a weekly plan's date range.

    Both the start and the end date are inclusive. Plan ranges may be
    clipped to a task's real dates, so this must not assume a full
    Monday-to-Sunday window.
    """

    return plan.week_start_date <= value <= plan.week_end_date
