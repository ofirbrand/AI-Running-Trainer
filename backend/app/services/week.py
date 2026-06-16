"""Calendar helpers for Israeli weeks (Sunday = first day of the week).

Python's ``date.weekday()`` returns Monday=0..Sunday=6. Throughout this app we
use an *Israeli* weekday index where Sunday=0..Saturday=6.
"""
from __future__ import annotations

from datetime import date, timedelta

WEEKDAY_NAMES = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def israeli_weekday(d: date) -> int:
    """Return 0 for Sunday .. 6 for Saturday."""
    return (d.weekday() + 1) % 7


def week_start(d: date) -> date:
    """Return the Sunday that begins the week containing ``d``."""
    return d - timedelta(days=israeli_weekday(d))


def week_end(d: date) -> date:
    """Return the Saturday that ends the week containing ``d``."""
    return week_start(d) + timedelta(days=6)


def week_dates(start: date) -> list[date]:
    """Return the seven dates (Sun..Sat) for the week starting at ``start``."""
    return [start + timedelta(days=i) for i in range(7)]


def weeks_between(start: date, end: date) -> int:
    """Number of Israeli weeks spanned from ``start`` to ``end`` inclusive."""
    s = week_start(start)
    e = week_start(end)
    return max(1, ((e - s).days // 7) + 1)


def week_number_for(plan_start: date, d: date) -> int:
    """1-based week index of ``d`` relative to a plan starting on ``plan_start``."""
    s = week_start(plan_start)
    delta_days = (week_start(d) - s).days
    return (delta_days // 7) + 1
