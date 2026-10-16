from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from receptionist.scheduling import (
    Interval,
    Rules,
    SchedulingError,
    Service,
    fmt_time,
    fmt_times,
    match_service,
    nearest,
    normalize_phone,
    parse_hours,
    parse_time,
    spread,
)

TZ = ZoneInfo("Asia/Kolkata")
HOURS = {d: "9 AM to 7 PM" for d in ("monday", "tuesday", "wednesday", "thursday", "friday")}
HOURS |= {"saturday": "10 AM to 2 PM", "sunday": "closed"}
MON = date(2026, 10, 19)
SAT = date(2026, 10, 17)
SUN = date(2026, 10, 18)
NOW = datetime(2026, 10, 14, 11, 0, tzinfo=TZ)  # Wednesday 11 AM
SERVICES = [
    Service("General check-up", timedelta(minutes=30)),
    Service("Teeth cleaning", timedelta(minutes=45)),
    Service("Tooth extraction", timedelta(minutes=45)),
]


@pytest.fixture
def rules():
    return Rules.from_config(HOURS, "Asia/Kolkata")


def at(d, h, m=0):
    return datetime.combine(d, time(h, m), tzinfo=TZ)


def test_parse_hours():
    assert parse_hours("9 AM to 7 PM") == (time(9), time(19))
    assert parse_hours("9:30 am - 6 pm") == (time(9, 30), time(18))
    assert parse_hours("closed") is None
    with pytest.raises(ValueError):
        parse_hours("nine to five")


@pytest.mark.parametrize("text,expected", [
    ("14:30", time(14, 30)), ("2:30 PM", time(14, 30)), ("2 pm", time(14)), ("10 a.m.", time(10)),
])
def test_parse_time(text, expected):
    assert parse_time(text) == expected


def test_slots_respect_hours_and_duration(rules):
    slots = rules.free_slots(SAT, timedelta(minutes=45), [], NOW)
    assert slots[0] == at(SAT, 10)
    assert slots[-1] == at(SAT, 13)  # 13:00 + 45 min fits before 14:00; 13:30 does not


def test_busy_time_is_skipped(rules):
    busy = [Interval(at(MON, 10), at(MON, 11))]
    slots = rules.free_slots(MON, timedelta(minutes=30), busy, NOW)
    assert at(MON, 10) not in slots and at(MON, 10, 30) not in slots
    assert at(MON, 9, 30) in slots and at(MON, 11) in slots


def test_service_cannot_overlap_into_busy(rules):
    busy = [Interval(at(MON, 10), at(MON, 11))]
    slots = rules.free_slots(MON, timedelta(minutes=45), busy, NOW)
    assert at(MON, 9, 30) not in slots  # 9:30-10:15 would overlap
    assert at(MON, 9) in slots


def test_closed_day_and_past_rejected(rules):
    with pytest.raises(SchedulingError, match="closed"):
        rules.free_slots(SUN, timedelta(minutes=30), [], NOW)
    with pytest.raises(SchedulingError, match="past"):
        rules.free_slots(date(2026, 10, 13), timedelta(minutes=30), [], NOW)


def test_too_far_ahead_rejected(rules):
    with pytest.raises(SchedulingError, match="days ahead"):
        rules.free_slots(date(2026, 12, 31), timedelta(minutes=30), [], NOW)


def test_minimum_notice_today(rules):
    slots = rules.free_slots(NOW.date(), timedelta(minutes=30), [], NOW)
    assert slots[0] == at(NOW.date(), 12)  # 11:00 now + 60 min notice


@pytest.mark.parametrize("raw", ["9876543210", "+91 98765 43210", "098765 43210", "98765-43210"])
def test_phone_normalised(raw):
    assert normalize_phone(raw) == "9876543210"


def test_short_phone_rejected():
    with pytest.raises(SchedulingError, match="9 digits"):
        normalize_phone("112233445")


@pytest.mark.parametrize("raw,expected", [
    ("teeth cleaning", "Teeth cleaning"),
    ("cleaning", "Teeth cleaning"),
    ("general checkup", "General check-up"),
    ("Tooth Extraction", "Tooth extraction"),
])
def test_service_matching(raw, expected):
    assert match_service(raw, SERVICES).name == expected


def test_unknown_service_lists_options():
    with pytest.raises(SchedulingError, match="Teeth cleaning"):
        match_service("hair cut", SERVICES)


def test_nearest_and_spread():
    slots = [at(MON, h) for h in range(9, 19)]
    assert nearest(slots, at(MON, 14, 15), 3) == [at(MON, 13), at(MON, 14), at(MON, 15)]
    picked = spread(slots, 4)
    assert picked[0] == at(MON, 9) and picked[-1] == at(MON, 18) and len(picked) == 4


def test_spoken_formats():
    assert fmt_time(at(MON, 10)) == "10 AM"
    assert fmt_time(at(MON, 14, 30)) == "2:30 PM"
    assert fmt_times([at(MON, 10), at(MON, 11)]) == "10 AM or 11 AM"
