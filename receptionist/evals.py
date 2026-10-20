"""Automated conversation tests ("evals").

Each scenario plays a scripted caller against the REAL agent (real prompt, real tools,
real LLM) on a fresh in-memory calendar, then checks the OUTCOME: was the right thing
booked / cancelled / moved, or correctly NOT done? Text only, no audio.

Run with:  python scripts/run_evals.py
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from receptionist.calendar_client import MemoryCalendar
from receptionist.scheduler import Scheduler
from receptionist.scheduling import fmt_day

PHONE = "9876543210"
OTHER_PHONE = "9123456780"


# ---------------------------------------------------------------- helpers


def open_day(s: Scheduler, after: int = 1, skip: int = 0) -> date:
    """The (skip+1)-th open day at least `after` days from today."""
    d = s.now().date() + timedelta(days=after)
    found = -1
    while True:
        if s.rules.opening(d) is not None:
            found += 1
            if found == skip:
                return d
        d += timedelta(days=1)


def next_closed_day(s: Scheduler) -> date | None:
    d = s.now().date() + timedelta(days=1)
    for _ in range(7):
        if s.rules.opening(d) is None:
            return d
        d += timedelta(days=1)
    return None


def say_day(d: date) -> str:
    return fmt_day(d)  # "Thursday, 15 October"


def at(s: Scheduler, d: date, hour: int, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=s.rules.tz)


@dataclass
class Transcript:
    lines: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    agent_replies: list[str] = field(default_factory=list)

    def said(self, *words: str) -> bool:
        text = " ".join(self.agent_replies).lower()
        return any(w.lower() in text for w in words)


Check = Callable[[MemoryCalendar, Scheduler, Transcript, dict], tuple[bool, str]]


@dataclass
class Scenario:
    name: str
    category: str  # booking | edge | change | reliability
    description: str
    turns: Callable[[Scheduler, dict], list[str]]
    check: Check
    seed: Callable[[Scheduler, dict], Awaitable[None]] | None = None


# ---------------------------------------------------------------- scenarios


def open_day_at(s: Scheduler, after: date, hour: int) -> date:
    """First day after `after` that is open from `hour` until at least hour+1."""
    d = after + timedelta(days=1)
    while True:
        span = s.rules.opening(d)
        if span and span[0].hour <= hour and span[1].hour >= hour + 1:
            return d
        d += timedelta(days=1)


def _ctx(s: Scheduler) -> dict:
    # d1: open from 11 AM to 1 PM (booking tests). d2: a later day open at 3 PM (reschedule).
    d1 = open_day_at(s, s.now().date(), 11)
    d2 = open_day_at(s, d1, 15)
    return {"d1": d1, "d2": d2, "closed": next_closed_day(s)}


async def _seed_mine(s: Scheduler, c: dict) -> None:
    await s.book("Rakesh Kumar", PHONE, "Teeth cleaning", c["d1"].isoformat(), "11:00")


async def _seed_other(s: Scheduler, c: dict) -> None:
    await s.book("Someone Else", OTHER_PHONE, "Teeth cleaning", c["d1"].isoformat(), "11:00")


def _booking_flow(c: dict, time_text: str = "11 AM", phone: str = "98765 43210") -> list[str]:
    return [
        f"Hi, I'd like to book a teeth cleaning on {say_day(c['d1'])} at {time_text}.",
        "My name is Rakesh Kumar.",
        f"My number is {phone}.",
        "Yes, that's correct.",
    ]


def _events_at(cal: MemoryCalendar, when: datetime) -> list:
    return [e for e in cal.events if e.start == when]


def check_booked_at(hour: int, minute: int = 0) -> Check:
    def check(cal, s, t, c):
        want = at(s, c["d1"], hour, minute)
        mine = [e for e in cal.events if e.phone == PHONE]
        if len(mine) == 1 and mine[0].start == want:
            return True, f"booked {mine[0].service} at {want:%a %H:%M}"
        got = [f"{e.start:%a %H:%M}" for e in mine]
        return False, f"expected one booking at {want:%a %H:%M}, got {got or 'none'}"

    return check


def check_nothing_booked(reason_words: tuple[str, ...] = ()) -> Check:
    def check(cal, s, t, c):
        mine = [e for e in cal.events if e.phone == PHONE]
        if mine:
            return False, f"should NOT have booked, but booked {mine[0].start:%a %H:%M}"
        if reason_words and not t.said(*reason_words):
            return False, f"no booking (good) but reply never mentioned {reason_words}"
        return True, "correctly did not book"

    return check


def check_slot_taken(cal, s, t, c):
    taken = at(s, c["d1"], 11)
    if len(_events_at(cal, taken)) != 1:
        return False, "double-booked the taken 11 AM slot"
    if not t.said("10:30", "11:30", "12", "10 am", "9:", "10:"):
        return False, "didn't offer alternative times"
    return True, "refused the taken slot and offered alternatives"


def check_cancelled(cal, s, t, c):
    if any(e.phone == PHONE for e in cal.events):
        return False, "appointment still in the calendar"
    return True, "appointment cancelled"


def check_not_cancelled(cal, s, t, c):
    if not any(e.phone == PHONE for e in cal.events):
        return False, "cancelled a booking for a number that didn't match"
    return True, "kept the booking (wrong number)"


def check_rescheduled(cal, s, t, c):
    mine = [e for e in cal.events if e.phone == PHONE]
    want = at(s, c["d2"], 15)
    if len(mine) == 1 and mine[0].start == want:
        return True, f"moved to {want:%a %H:%M}"
    got = [f"{e.start:%a %H:%M}" for e in mine]
    return False, f"expected the booking at {want:%a %H:%M}, got {got or 'none'}"


def check_asks_for_day(cal, s, t, c):
    if cal.events:
        return False, "booked without knowing the day"
    if not t.said("day", "date", "when"):
        return False, "didn't ask which day"
    return True, "asked for the missing day"


SCENARIOS: list[Scenario] = [
    Scenario(
        "book_happy_path", "booking", "Full booking with all details",
        lambda s, c: _booking_flow(c), check_booked_at(11),
    ),
    Scenario(
        "slot_taken", "booking", "Requested time is already booked by someone else",
        lambda s, c: [f"Can I get a teeth cleaning on {say_day(c['d1'])} at 11 AM?"],
        check_slot_taken, seed=_seed_other,
    ),
    Scenario(
        "change_of_mind", "reliability", "Caller changes the time mid-booking",
        lambda s, c: [
            f"I'd like a teeth cleaning on {say_day(c['d1'])} at 11 AM.",
            "Actually, can we make it 12 PM instead?",
            "My name is Rakesh Kumar.",
            "My number is 98765 43210.",
            "Yes, that's correct.",
        ],
        check_booked_at(12),
    ),
    Scenario(
        "incomplete_request", "reliability", "Caller asks to book but gives no day",
        lambda s, c: ["I want to book a check-up."], check_asks_for_day,
    ),
    Scenario(
        "short_phone_number", "edge", "Phone number is missing a digit",
        lambda s, c: _booking_flow(c, phone="98765 4321"), check_nothing_booked(),
    ),
    Scenario(
        "no_confirmation", "edge", "Caller changes their mind at the read-back",
        lambda s, c: _booking_flow(c)[:3] + ["Wait, hold on, I need to check my schedule first."],
        check_nothing_booked(),
    ),
    Scenario(
        "closed_day", "edge", "Caller asks for a day the clinic is closed",
        lambda s, c: [f"Can I come in for a check-up on {say_day(c['closed'])}?"],
        check_nothing_booked(("closed",)),
    ),
    Scenario(
        "unknown_service", "edge", "Caller asks for a service that isn't offered",
        lambda s, c: [f"Can you book me teeth whitening on {say_day(c['d1'])} at 11 AM?"],
        check_nothing_booked(("cleaning", "check-up", "extraction", "offer", "don't")),
    ),
    Scenario(
        "cancel", "change", "Caller cancels their appointment",
        lambda s, c: [
            "Hi, I need to cancel my appointment.",
            "The number is 98765 43210.",
            "Yes, please cancel it.",
        ],
        check_cancelled, seed=_seed_mine,
    ),
    Scenario(
        "cancel_wrong_number", "change", "Cancel request with a number that has no booking",
        lambda s, c: [
            "I want to cancel my appointment.",
            "My number is 91234 56780.",
            "Yes, cancel it.",
        ],
        check_not_cancelled, seed=_seed_mine,
    ),
    Scenario(
        "reschedule", "change", "Caller moves their appointment to another day",
        lambda s, c: [
            "Hi, I need to move my appointment.",
            "My number is 98765 43210.",
            f"Can we do {say_day(c['d2'])} at 3 PM instead?",
            "Yes, that's correct.",
        ],
        check_rescheduled, seed=_seed_mine,
    ),
]


# ---------------------------------------------------------------- runner


@dataclass
class EvalResult:
    name: str
    category: str
    passed: bool
    reason: str
    seconds: float
    turns: int
    transcript: list[str]
    error: str = ""


def _record(result, transcript: Transcript) -> None:
    for ev in getattr(result, "events", []):
        item = getattr(ev, "item", None)
        kind = getattr(ev, "type", "") or getattr(item, "type", "")
        if kind == "message" and getattr(item, "role", "") == "assistant":
            text = getattr(item, "text_content", "") or ""
            transcript.agent_replies.append(text)
            transcript.lines.append(f"ARIA: {text}")
        elif kind == "function_call":
            call = f"{item.name}({item.arguments})"
            transcript.tool_calls.append(call)
            transcript.lines.append(f"  -> {call}")
        elif kind == "function_call_output":
            transcript.lines.append(f"  <- {getattr(item, 'output', '')}")


async def run_scenario(sc: Scenario, llm, make_scheduler, agent_cls) -> EvalResult:
    """make_scheduler() -> fresh Scheduler on a MemoryCalendar. agent_cls(scheduler) -> Agent."""
    from livekit.agents import AgentSession

    scheduler = make_scheduler()
    cal: MemoryCalendar = scheduler.calendar  # type: ignore[assignment]
    ctx = _ctx(scheduler)
    if sc.seed:
        await sc.seed(scheduler, ctx)
    transcript = Transcript()
    started = time.perf_counter()
    turns = sc.turns(scheduler, ctx)
    try:
        async with AgentSession(llm=llm) as session:
            await session.start(agent_cls(scheduler))
            for text in turns:
                transcript.lines.append(f"CALLER: {text}")
                result = await session.run(user_input=text)
                _record(result, transcript)
        passed, reason = sc.check(cal, scheduler, transcript, ctx)
        error = ""
    except Exception as e:  # noqa: BLE001
        passed, reason, error = False, "crashed", f"{type(e).__name__}: {e}"
    return EvalResult(
        sc.name, sc.category, passed, reason, round(time.perf_counter() - started, 1),
        len(turns), transcript.lines, error,
    )
