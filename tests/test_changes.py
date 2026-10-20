"""Day 5: find, cancel and reschedule bookings."""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from receptionist.calendar_client import MemoryCalendar
from receptionist.scheduler import Scheduler, build_rules, services_from_config
from receptionist.scheduling import Interval, subtract

TZ = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 14, 11, 0, tzinfo=TZ)  # Wednesday
HOURS = {d: "9 AM to 7 PM" for d in ("monday", "tuesday", "wednesday", "thursday", "friday")}
HOURS |= {"saturday": "10 AM to 2 PM", "sunday": "closed"}
SERVICES = services_from_config([
    {"name": "General check-up", "duration_minutes": 30},
    {"name": "Teeth cleaning", "duration_minutes": 45},
])
PHONE = "9876543210"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def setup():
    cal = MemoryCalendar()
    rules = build_rules(HOURS, "Asia/Kolkata", 30, 60, 30)
    s = Scheduler(cal, rules, SERVICES, "Sunrise Dental", clock=lambda: NOW)
    run(s.book("Rakesh Kumar", PHONE, "cleaning", "2026-10-15", "11:00"))
    return s, cal


def at(h, m=0, day=15):
    return datetime(2026, 10, day, h, m, tzinfo=TZ)


def test_subtract_cuts_own_slot_out_of_merged_block():
    busy = [Interval(at(10), at(12))]  # someone 10-11 + our booking 11-12, merged by Google
    assert subtract(busy, Interval(at(11), at(12))) == [Interval(at(10), at(11))]
    assert subtract(busy, Interval(at(14), at(15))) == busy


def test_find_by_phone(setup):
    s, _ = setup
    out = run(s.find_bookings("+91 98765 43210"))
    assert out.startswith("FOUND: 1") and "Teeth cleaning" in out and "Rakesh Kumar" in out
    assert "11 AM" in out


def test_find_wrong_number(setup):
    s, _ = setup
    assert run(s.find_bookings("9123456780")).startswith("NOT FOUND")
    assert run(s.find_bookings("12345")).startswith("NOT FOUND")  # too short


def test_cancel(setup):
    s, cal = setup
    out = run(s.cancel(PHONE, "2026-10-15"))
    assert out.startswith("CANCELLED") and cal.events == []


def test_cancel_wrong_day_keeps_booking(setup):
    s, cal = setup
    out = run(s.cancel(PHONE, "2026-10-16"))
    assert out.startswith("NOT CANCELLED") and len(cal.events) == 1


def test_cannot_cancel_someone_elses_booking(setup):
    s, cal = setup
    assert run(s.cancel("9123456780", "2026-10-15")).startswith("NOT CANCELLED")
    assert len(cal.events) == 1


def test_reschedule_to_another_day(setup):
    s, cal = setup
    out = run(s.reschedule(PHONE, "2026-10-15", "2026-10-16", "15:00"))
    assert out.startswith("RESCHEDULED") and "3 PM" in out
    assert cal.events[0].start == at(15, day=16)
    assert cal.events[0].end - cal.events[0].start == timedelta(minutes=45)


def test_reschedule_overlapping_its_own_old_slot(setup):
    s, cal = setup  # 11:00-11:45 -> 11:30-12:15 overlaps itself; must still work
    out = run(s.reschedule(PHONE, "2026-10-15", "2026-10-15", "11:30"))
    assert out.startswith("RESCHEDULED")
    assert cal.events[0].start == at(11, 30)


def test_reschedule_into_someone_else_is_refused(setup):
    s, cal = setup
    run(s.book("Other Person", "9123456780", "check-up", "2026-10-16", "15:00"))
    out = run(s.reschedule(PHONE, "2026-10-15", "2026-10-16", "15:00"))
    assert out.startswith("NOT RESCHEDULED") and "Closest free times" in out
    assert next(e for e in cal.events if e.phone == PHONE).start == at(11)


@pytest.mark.parametrize("new_date,new_time,reason", [
    ("2026-10-18", "11:00", "closed"),
    ("2026-10-15", "20:00", "not available"),
    ("2026-10-15", "11:00", "already"),
])
def test_reschedule_rules(setup, new_date, new_time, reason):
    s, cal = setup
    out = run(s.reschedule(PHONE, "2026-10-15", new_date, new_time))
    assert out.startswith("NOT RESCHEDULED") and reason in out
    assert cal.events[0].start == at(11)
