import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from receptionist.calendar_client import CalendarError, MemoryCalendar
from receptionist.scheduler import Scheduler, build_rules, services_from_config

TZ = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 14, 11, 0, tzinfo=TZ)  # Wednesday
HOURS = {d: "9 AM to 7 PM" for d in ("monday", "tuesday", "wednesday", "thursday", "friday")}
HOURS |= {"saturday": "10 AM to 2 PM", "sunday": "closed"}
SERVICES = services_from_config([
    {"name": "General check-up", "duration_minutes": 30},
    {"name": "Tooth extraction", "duration_minutes": 45},
])


def make(calendar=None):
    cal = calendar or MemoryCalendar()
    rules = build_rules(HOURS, "Asia/Kolkata", 30, 60, 30)
    return Scheduler(cal, rules, SERVICES, "Sunrise Dental Clinic", clock=lambda: NOW), cal


def run(coro):
    return asyncio.run(coro)


def test_check_free_time():
    s, _ = make()
    out = run(s.check_availability("2026-10-15", "check-up", "10:00"))
    assert out.startswith("AVAILABLE") and "10 AM" in out


def test_book_then_slot_is_taken():
    s, cal = make()
    out = run(s.book("Rakesh Kumar", "98765 43210", "check-up", "2026-10-15", "10:00"))
    assert out.startswith("BOOKED") and "3210" in out
    assert len(cal.events) == 1
    again = run(s.book("Someone Else", "9123456780", "check-up", "2026-10-15", "10:00"))
    assert again.startswith("NOT BOOKED") and "Closest free times" in again
    check = run(s.check_availability("2026-10-15", "check-up", "10:00"))
    assert check.startswith("UNAVAILABLE") and "10:30 AM" in check


@pytest.mark.parametrize("kwargs,reason", [
    (dict(phone="112233445"), "9 digits"),
    (dict(date_text="2026-10-18"), "closed"),
    (dict(date_text="2026-10-01"), "past"),
    (dict(time_text="20:00"), "not available"),
    (dict(service_text="hair cut"), "not a service"),
    (dict(name=""), "name is missing"),
])
def test_invalid_bookings_rejected(kwargs, reason):
    s, cal = make()
    args = dict(name="Rakesh", phone="9876543210", service_text="check-up",
                date_text="2026-10-15", time_text="10:00") | kwargs
    out = run(s.book(**args))
    assert out.startswith("NOT BOOKED") and reason in out
    assert cal.events == []


def test_calendar_down_is_reported():
    class Broken(MemoryCalendar):
        async def busy(self, start, end):
            raise CalendarError("boom")

    s, _ = make(Broken())
    assert run(s.check_availability("2026-10-15", "check-up")).startswith("ERROR")
    assert run(s.book("Rakesh", "9876543210", "check-up", "2026-10-15", "10:00")).startswith(
        "NOT BOOKED"
    )


def test_concurrent_bookings_cannot_double_book():
    s, cal = make()

    async def both():
        return await asyncio.gather(
            s.book("A Person", "9876543210", "check-up", "2026-10-15", "10:00"),
            s.book("B Person", "9123456780", "check-up", "2026-10-15", "10:00"),
        )

    results = run(both())
    assert sum(r.startswith("BOOKED") for r in results) == 1
    assert len(cal.events) == 1
