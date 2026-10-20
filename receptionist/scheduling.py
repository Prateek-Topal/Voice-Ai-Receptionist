"""Scheduling rules: opening hours, free slots, and booking validation.

Pure Python (no Google, no LiveKit) so every rule is unit-tested.
The LLM is never trusted to get these right: the tools call these functions and
reject anything invalid before it reaches the calendar.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

_HOURS_RE = re.compile(
    r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*(?:to|-|–)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*$",
    re.IGNORECASE,
)


class SchedulingError(ValueError):
    """A booking request that breaks a rule. The message is shown to the LLM."""


@dataclass(frozen=True)
class Service:
    name: str
    duration: timedelta


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end


# ---------------------------------------------------------------- parsing


def _to_time(hour: str, minute: str | None, ampm: str) -> time:
    h = int(hour) % 12 + (12 if ampm.lower() == "pm" else 0)
    return time(h, int(minute or 0))


def parse_hours(text: str) -> tuple[time, time] | None:
    """'9 AM to 7 PM' -> (09:00, 19:00). 'closed' -> None."""
    if not text or str(text).strip().lower() in ("closed", "off", "none"):
        return None
    m = _HOURS_RE.match(str(text))
    if not m:
        raise ValueError(f"Can't read opening hours {text!r}. Use a format like '9 AM to 7 PM'.")
    opens = _to_time(m.group(1), m.group(2), m.group(3))
    closes = _to_time(m.group(4), m.group(5), m.group(6))
    if closes <= opens:
        raise ValueError(f"Closing time must be after opening time in {text!r}")
    return opens, closes


def parse_date(text: str) -> date:
    try:
        return date.fromisoformat(str(text).strip())
    except ValueError as e:
        raise SchedulingError(
            f"'{text}' is not a valid date. Use the format YYYY-MM-DD, "
            "worked out from today's date."
        ) from e


def parse_time(text: str) -> time:
    raw = str(text).strip().lower().replace(".", "")
    for fmt in ("%H:%M", "%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    raise SchedulingError(f"'{text}' is not a valid time. Use 24-hour HH:MM, for example 14:30.")


def normalize_phone(text: str, digits: int = 10) -> str:
    """Keep digits only; strip an Indian +91 / 0 prefix. Raises if the length is wrong."""
    only = re.sub(r"\D", "", str(text))
    if len(only) == digits + 2 and only.startswith("91"):
        only = only[2:]
    elif len(only) == digits + 1 and only.startswith("0"):
        only = only[1:]
    if len(only) != digits:
        raise SchedulingError(
            f"The phone number has {len(only)} digits but should have {digits}. "
            "Ask the caller to repeat the full number."
        )
    return only


def match_service(requested: str, services: list[Service]) -> Service:
    """Find the service the caller means. Tolerant of case and small wording differences."""
    want = str(requested).strip().lower()
    by_name = {s.name.lower(): s for s in services}
    if want in by_name:
        return by_name[want]
    for name, svc in by_name.items():
        if want and (want in name or name in want):
            return svc
    close = difflib.get_close_matches(want, list(by_name), n=1, cutoff=0.6)
    if close:
        return by_name[close[0]]
    names = ", ".join(s.name for s in services)
    raise SchedulingError(
        f"'{requested}' is not a service we offer. Available services: {names}. "
        "Ask the caller which of these they want."
    )


# ---------------------------------------------------------------- slots


@dataclass
class Rules:
    hours: dict[str, tuple[time, time] | None]
    tz: ZoneInfo
    slot_step: timedelta = timedelta(minutes=30)
    min_notice: timedelta = timedelta(minutes=60)
    horizon: timedelta = timedelta(days=30)

    @classmethod
    def from_config(cls, hours: dict[str, str], tz: str, **kw) -> Rules:
        parsed = {d: parse_hours(hours.get(d, "closed")) for d in DAYS}
        return cls(hours=parsed, tz=ZoneInfo(tz), **kw)

    def opening(self, day: date) -> tuple[datetime, datetime] | None:
        span = self.hours.get(DAYS[day.weekday()])
        if span is None:
            return None
        return (
            datetime.combine(day, span[0], tzinfo=self.tz),
            datetime.combine(day, span[1], tzinfo=self.tz),
        )

    def check_day(self, day: date, now: datetime) -> tuple[datetime, datetime]:
        today = now.astimezone(self.tz).date()
        if day < today:
            raise SchedulingError(f"{fmt_day(day)} is in the past. Ask for a future day.")
        if day > (now + self.horizon).date():
            days = self.horizon.days
            raise SchedulingError(f"We only book up to {days} days ahead. Ask for an earlier day.")
        span = self.opening(day)
        if span is None:
            raise SchedulingError(f"The clinic is closed on {fmt_day(day)}. Offer another day.")
        return span

    def free_slots(
        self, day: date, duration: timedelta, busy: list[Interval], now: datetime
    ) -> list[datetime]:
        """Start times on `day` where the service fits, respecting hours, notice and busy times."""
        opens, closes = self.check_day(day, now)
        earliest = now.astimezone(self.tz) + self.min_notice
        slots = []
        start = opens
        while start + duration <= closes:
            candidate = Interval(start, start + duration)
            if start >= earliest and not any(candidate.overlaps(b) for b in busy):
                slots.append(start)
            start += self.slot_step
        return slots


def subtract(busy: list[Interval], own: Interval) -> list[Interval]:
    """Busy time minus one booking, so a reschedule doesn't collide with itself.

    Google's freebusy merges back-to-back events, so the booking is cut out of whichever
    busy blocks contain it rather than removed as a whole block.
    """
    out = []
    for b in busy:
        if not b.overlaps(own):
            out.append(b)
            continue
        if b.start < own.start:
            out.append(Interval(b.start, own.start))
        if own.end < b.end:
            out.append(Interval(own.end, b.end))
    return out


def nearest(slots: list[datetime], target: datetime, n: int = 3) -> list[datetime]:
    """The n free slots closest to what the caller asked for, in time order."""
    return sorted(sorted(slots, key=lambda s: abs((s - target).total_seconds()))[:n])


def spread(slots: list[datetime], n: int = 4) -> list[datetime]:
    """Pick n slots spread across the day, so the caller hears morning and afternoon options."""
    if len(slots) <= n:
        return slots
    step = (len(slots) - 1) / (n - 1)
    return [slots[round(i * step)] for i in range(n)]


# ---------------------------------------------------------------- speaking


def fmt_day(day: date) -> str:
    return f"{day:%A}, {day.day} {day:%B}"


def fmt_time(t: datetime | time) -> str:
    return t.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def fmt_times(slots: list[datetime]) -> str:
    times = [fmt_time(s) for s in slots]
    return times[0] if len(times) == 1 else ", ".join(times[:-1]) + " or " + times[-1]
