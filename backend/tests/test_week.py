"""Unit tests for Israeli-week calendar helpers (Sunday = day 0)."""
from datetime import date

from app.services import week


def test_israeli_weekday():
    # 2026-06-14 is a Sunday.
    assert week.israeli_weekday(date(2026, 6, 14)) == 0
    assert week.israeli_weekday(date(2026, 6, 15)) == 1  # Monday
    assert week.israeli_weekday(date(2026, 6, 20)) == 6  # Saturday


def test_week_start_and_end():
    d = date(2026, 6, 17)  # Wednesday
    assert week.week_start(d) == date(2026, 6, 14)  # the Sunday
    assert week.week_end(d) == date(2026, 6, 20)  # the Saturday


def test_week_start_on_sunday_is_same_day():
    sunday = date(2026, 6, 14)
    assert week.week_start(sunday) == sunday


def test_week_dates():
    dates = week.week_dates(date(2026, 6, 14))
    assert len(dates) == 7
    assert dates[0] == date(2026, 6, 14)
    assert dates[-1] == date(2026, 6, 20)


def test_weeks_between():
    assert week.weeks_between(date(2026, 6, 14), date(2026, 6, 20)) == 1
    assert week.weeks_between(date(2026, 6, 14), date(2026, 6, 21)) == 2
    assert week.weeks_between(date(2026, 6, 14), date(2026, 7, 11)) == 4


def test_week_number_for():
    start = date(2026, 6, 14)  # Sunday
    assert week.week_number_for(start, date(2026, 6, 14)) == 1
    assert week.week_number_for(start, date(2026, 6, 20)) == 1
    assert week.week_number_for(start, date(2026, 6, 21)) == 2
