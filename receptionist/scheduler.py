"""Availability checks and bookings, as used by Aria's tools.

Every method returns a short plain-English result for the LLM. Results start with a
status word (AVAILABLE / UNAVAILABLE / BOOKED / NOT BOOKED / ERROR) so the model can't
confuse a failed booking with a successful one.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

from receptionist.calendar_client import BookedEvent, Calendar, CalendarError
from receptionist.scheduling import (
    Interval,
    Rules,
    SchedulingError,
    Service,
    fmt_day,
    fmt_time,
    fmt_times,
    match_service,
    nearest,
    normalize_phone,
    parse_date,
    parse_time,
    spread,
    subtract,
)

logger = logging.getLogger("receptionist.scheduler")

CALENDAR_DOWN = (
    "ERROR: the booking calendar can't be reached right now. Apologise, take the caller's "
    "name, number and preferred time, and say the team will call back to confirm."
)


class Scheduler:
    def __init__(
        self,
        calendar: Calendar,
        rules: Rules,
        services: list[Service],
        business_name: str,
        phone_digits: int = 10,
        clock=None,
    ) -> None:
        self.calendar = calendar
        self.rules = rules
        self.services = services
        self.business_name = business_name
        self.phone_digits = phone_digits
        self._clock = clock or (lambda: datetime.now(rules.tz))
        self._lock = asyncio.Lock()  # no two bookings race for the same slot

    def now(self) -> datetime:
        return self._clock()

    async def _free_slots(self, day: date, service: Service) -> list[datetime]:
        opens, closes = self.rules.check_day(day, self.now())
        busy = await self.calendar.busy(opens, closes)
        return self.rules.free_slots(day, service.duration, busy, self.now())

    # ------------------------------------------------------------ tools

    async def check_availability(
        self, date_text: str, service_text: str, preferred_time: str | None = None
    ) -> str:
        try:
            day = parse_date(date_text)
            service = match_service(service_text, self.services)
            slots = await self._free_slots(day, service)
        except SchedulingError as e:
            return f"UNAVAILABLE: {e}"
        except CalendarError as e:
            logger.error("calendar error during availability check: %s", e)
            return CALENDAR_DOWN

        label = f"{service.name} on {fmt_day(day)}"
        logger.info("availability %s (%s): %d free slots", label, preferred_time, len(slots))
        if not slots:
            return f"UNAVAILABLE: no free times left for {label}. Offer another day."

        if preferred_time:
            try:
                wanted = datetime.combine(day, parse_time(preferred_time), tzinfo=self.rules.tz)
            except SchedulingError as e:
                return f"UNAVAILABLE: {e}"
            if wanted in slots:
                return f"AVAILABLE: {fmt_time(wanted)} is free for {label}."
            options = fmt_times(nearest(slots, wanted))
            return (
                f"UNAVAILABLE: {fmt_time(wanted)} is not free for {label}. "
                f"Closest free times: {options}. Offer these."
            )

        return f"AVAILABLE: free times for {label} include {fmt_times(spread(slots))}."

    async def book(
        self, name: str, phone: str, service_text: str, date_text: str, time_text: str
    ) -> str:
        try:
            if not str(name).strip() or len(str(name).strip()) < 2:
                raise SchedulingError("The caller's name is missing. Ask for their full name.")
            number = normalize_phone(phone, self.phone_digits)
            service = match_service(service_text, self.services)
            day = parse_date(date_text)
            start = datetime.combine(day, parse_time(time_text), tzinfo=self.rules.tz)
        except SchedulingError as e:
            return f"NOT BOOKED: {e}"

        async with self._lock:
            try:
                # Re-check right before writing, in case the slot was taken a moment ago.
                slots = await self._free_slots(day, service)
            except SchedulingError as e:
                return f"NOT BOOKED: {e}"
            except CalendarError as e:
                logger.error("calendar error before booking: %s", e)
                return CALENDAR_DOWN.replace("ERROR:", "NOT BOOKED:")

            if start not in slots:
                options = fmt_times(nearest(slots, start)) if slots else "none that day"
                return (
                    f"NOT BOOKED: {fmt_time(start)} on {fmt_day(day)} is not available for "
                    f"{service.name}. Closest free times: {options}."
                )

            end = start + service.duration
            summary = f"{service.name} – {name.strip()}"
            description = (
                f"Patient: {name.strip()}\nPhone: {number}\nService: {service.name}\n"
                f"Booked by Aria (AI receptionist) on {self.now():%d %b %Y %H:%M}."
            )
            try:
                event = await self.calendar.create(
                    start, end, summary, description, number, name.strip(), service.name
                )
            except CalendarError as e:
                logger.error("calendar error while booking: %s", e)
                return CALENDAR_DOWN.replace("ERROR:", "NOT BOOKED:")

        logger.info("BOOKED %s %s %s (event %s)", service.name, start.isoformat(), number, event.id)
        return (
            f"BOOKED: {service.name} for {name.strip()} on {fmt_day(day)} at {fmt_time(start)}, "
            f"phone ending {number[-4:]}. Tell the caller it is confirmed."
        )


    # ------------------------------------------------------------ Day 5: changes

    def _describe(self, ev: BookedEvent) -> str:
        what = ev.service or ev.summary
        who = f" for {ev.name}" if ev.name else ""
        return f"{what}{who} on {fmt_day(ev.start.date())} at {fmt_time(ev.start)}"

    async def _upcoming(self, number: str) -> list[BookedEvent]:
        now = self.now()
        return await self.calendar.find(number, now, now + self.rules.horizon + timedelta(days=60))

    async def _locate(self, number: str, date_text: str, time_text: str | None) -> BookedEvent:
        """The caller's booking on that day (and time, if several). Raises SchedulingError."""
        day = parse_date(date_text)
        events = [e for e in await self._upcoming(number) if e.start.date() == day]
        if time_text:
            wanted = parse_time(time_text)
            events = [e for e in events if e.start.time().replace(tzinfo=None) == wanted]
        if not events:
            raise SchedulingError(
                f"No appointment found on {fmt_day(day)} for the number ending {number[-4:]}. "
                "Use find_booking to see the caller's appointments."
            )
        if len(events) > 1:
            times = fmt_times([e.start for e in events])
            raise SchedulingError(f"Several appointments that day ({times}). Ask which one.")
        return events[0]

    async def find_bookings(self, phone: str) -> str:
        try:
            number = normalize_phone(phone, self.phone_digits)
            events = await self._upcoming(number)
        except SchedulingError as e:
            return f"NOT FOUND: {e}"
        except CalendarError as e:
            logger.error("calendar error during lookup: %s", e)
            return CALENDAR_DOWN
        logger.info("lookup %s: %d upcoming", number[-4:], len(events))
        if not events:
            return (
                f"NOT FOUND: no upcoming appointments for the number ending {number[-4:]}. "
                "Read the number back to check it, or ask if they booked with another number."
            )
        listed = "; ".join(self._describe(e) for e in events[:5])
        return f"FOUND: {len(events)} upcoming appointment(s): {listed}."

    async def cancel(self, phone: str, date_text: str, time_text: str | None = None) -> str:
        try:
            number = normalize_phone(phone, self.phone_digits)
            async with self._lock:
                event = await self._locate(number, date_text, time_text)
                await self.calendar.delete(event.id)
        except SchedulingError as e:
            return f"NOT CANCELLED: {e}"
        except CalendarError as e:
            logger.error("calendar error while cancelling: %s", e)
            return CALENDAR_DOWN.replace("ERROR:", "NOT CANCELLED:")
        logger.info("CANCELLED %s (event %s)", self._describe(event), event.id)
        return f"CANCELLED: {self._describe(event)}. Tell the caller it is cancelled."

    async def reschedule(
        self,
        phone: str,
        current_date: str,
        new_date: str,
        new_time: str,
        current_time: str | None = None,
    ) -> str:
        try:
            number = normalize_phone(phone, self.phone_digits)
            day = parse_date(new_date)
            start = datetime.combine(day, parse_time(new_time), tzinfo=self.rules.tz)
        except SchedulingError as e:
            return f"NOT RESCHEDULED: {e}"

        async with self._lock:
            try:
                event = await self._locate(number, current_date, current_time)
                service = match_service(event.service or event.summary, self.services)
                opens, closes = self.rules.check_day(day, self.now())
                busy = await self.calendar.busy(opens, closes)
                busy = subtract(busy, Interval(event.start, event.end))  # ignore its own slot
                slots = self.rules.free_slots(day, service.duration, busy, self.now())
            except SchedulingError as e:
                return f"NOT RESCHEDULED: {e}"
            except CalendarError as e:
                logger.error("calendar error before rescheduling: %s", e)
                return CALENDAR_DOWN.replace("ERROR:", "NOT RESCHEDULED:")

            if start == event.start:
                return f"NOT RESCHEDULED: the appointment is already at {fmt_time(start)} then."
            if start not in slots:
                options = fmt_times(nearest(slots, start)) if slots else "none that day"
                return (
                    f"NOT RESCHEDULED: {fmt_time(start)} on {fmt_day(day)} is not available. "
                    f"Closest free times: {options}."
                )
            old = self._describe(event)
            try:
                await self.calendar.move(event.id, start, start + service.duration)
            except CalendarError as e:
                logger.error("calendar error while rescheduling: %s", e)
                return CALENDAR_DOWN.replace("ERROR:", "NOT RESCHEDULED:")

        logger.info("RESCHEDULED %s -> %s", old, start.isoformat())
        return (
            f"RESCHEDULED: {service.name} moved from {old.split(' on ', 1)[-1]} to "
            f"{fmt_day(day)} at {fmt_time(start)}. Tell the caller the new time."
        )


def build_rules(hours: dict, timezone: str, slot_minutes: int, notice_minutes: int,
                horizon_days: int) -> Rules:
    return Rules.from_config(
        hours,
        timezone,
        slot_step=timedelta(minutes=slot_minutes),
        min_notice=timedelta(minutes=notice_minutes),
        horizon=timedelta(days=horizon_days),
    )


def services_from_config(raw: list[dict]) -> list[Service]:
    return [Service(s["name"], timedelta(minutes=int(s.get("duration_minutes", 30)))) for s in raw]


__all__ = ["Scheduler", "Interval", "build_rules", "services_from_config"]
