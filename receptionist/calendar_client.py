"""Calendar backends.

GoogleCalendar   real bookings via a Google service account
MemoryCalendar   in-memory, for tests and for running without Google credentials

The Google client library is synchronous, so every call runs in a worker thread
(asyncio.to_thread) and never blocks the voice pipeline.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from receptionist.scheduling import Interval

logger = logging.getLogger("receptionist.calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


@dataclass
class BookedEvent:
    id: str
    start: datetime
    end: datetime
    summary: str
    link: str = ""


class Calendar(Protocol):
    async def busy(self, start: datetime, end: datetime) -> list[Interval]: ...

    async def create(
        self, start: datetime, end: datetime, summary: str, description: str, phone: str
    ) -> BookedEvent: ...

    async def delete(self, event_id: str) -> None: ...


class CalendarError(RuntimeError):
    """The calendar could not be reached or refused the request."""


# ---------------------------------------------------------------- in-memory


@dataclass
class MemoryCalendar:
    events: list[BookedEvent] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    async def busy(self, start: datetime, end: datetime) -> list[Interval]:
        window = Interval(start, end)
        spans = [Interval(e.start, e.end) for e in self.events]
        return [span for span in spans if span.overlaps(window)]

    async def create(self, start, end, summary, description, phone) -> BookedEvent:
        event = BookedEvent(id=f"mem-{next(self._ids)}", start=start, end=end, summary=summary)
        self.events.append(event)
        return event

    async def delete(self, event_id: str) -> None:
        self.events = [e for e in self.events if e.id != event_id]


# ---------------------------------------------------------------- Google


class GoogleCalendar:
    def __init__(self, calendar_id: str, credentials_file: str | Path, timezone: str) -> None:
        self.calendar_id = calendar_id
        self.credentials_file = Path(credentials_file)
        self.timezone = timezone
        self._service = None

    def _svc(self):
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            if not self.credentials_file.exists():
                raise CalendarError(f"Service account file not found: {self.credentials_file}")
            creds = service_account.Credentials.from_service_account_file(
                str(self.credentials_file), scopes=SCOPES
            )
            self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # -- sync implementations (run in a thread) --

    def _busy_sync(self, start: datetime, end: datetime) -> list[Interval]:
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": self.timezone,
            "items": [{"id": self.calendar_id}],
        }
        resp = self._svc().freebusy().query(body=body).execute()
        cal = resp.get("calendars", {}).get(self.calendar_id, {})
        if cal.get("errors"):
            reasons = ", ".join(e.get("reason", "?") for e in cal["errors"])
            raise CalendarError(
                f"Google Calendar refused access ({reasons}). Is the calendar shared with the "
                "service account with 'Make changes to events'?"
            )
        return [
            Interval(datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in cal.get("busy", [])
        ]

    def _create_sync(self, start, end, summary, description, phone) -> BookedEvent:
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": self.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self.timezone},
            # Searchable later (Day 5: cancel / reschedule by phone number).
            "extendedProperties": {"private": {"phone": phone, "source": "aria"}},
        }
        ev = self._svc().events().insert(calendarId=self.calendar_id, body=body).execute()
        return BookedEvent(
            id=ev["id"], start=start, end=end, summary=summary, link=ev.get("htmlLink", "")
        )

    def _delete_sync(self, event_id: str) -> None:
        self._svc().events().delete(calendarId=self.calendar_id, eventId=event_id).execute()

    # -- async API --

    async def busy(self, start: datetime, end: datetime) -> list[Interval]:
        return await self._call(self._busy_sync, start, end)

    async def create(self, start, end, summary, description, phone) -> BookedEvent:
        return await self._call(self._create_sync, start, end, summary, description, phone)

    async def delete(self, event_id: str) -> None:
        await self._call(self._delete_sync, event_id)

    async def _call(self, fn, *args):
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=10)
        except CalendarError:
            raise
        except TimeoutError as e:
            raise CalendarError("Google Calendar did not respond in time") from e
        except Exception as e:  # googleapiclient.errors.HttpError, network errors, ...
            raise CalendarError(f"Google Calendar error: {e}") from e
