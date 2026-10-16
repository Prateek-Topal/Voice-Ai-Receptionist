"""Test the Google Calendar connection without voice.

  python scripts/check_calendar.py              read-only: show free slots for the next open days
  python scripts/check_calendar.py --test-book  also create a test appointment, then delete it
"""

import argparse
import asyncio
import logging
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from receptionist.calendar_client import CalendarError, GoogleCalendar  # noqa: E402
from receptionist.config import load_settings  # noqa: E402
from receptionist.persona import Persona  # noqa: E402
from receptionist.providers import build_scheduler  # noqa: E402
from receptionist.scheduling import fmt_day, fmt_times, spread  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def main(test_book: bool) -> int:
    settings = load_settings()
    persona = Persona.from_yaml(settings.business_config_path)
    scheduler = build_scheduler(settings, persona)
    cal = scheduler.calendar
    if not isinstance(cal, GoogleCalendar):
        print("\nFAIL: not using Google Calendar (see the warning above). "
              "Set GOOGLE_CALENDAR_ID and put the key file in credentials/.")
        return 1

    service = scheduler.services[0]
    print(f"\nCalendar: {settings.google_calendar_id}")
    print(f"Checking free slots for '{service.name}' ({service.duration.seconds // 60} min)\n")

    day, shown, first_free = scheduler.now().date(), 0, None
    try:
        while shown < 3 and day <= scheduler.now().date() + timedelta(days=14):
            if scheduler.rules.opening(day):
                slots = await scheduler._free_slots(day, service)
                text = fmt_times(spread(slots, 5)) if slots else "fully booked / too soon"
                print(f"  {fmt_day(day):<28} {len(slots):>2} free  e.g. {text}")
                if slots and first_free is None:
                    first_free = slots[0]
                shown += 1
            day += timedelta(days=1)
    except CalendarError as e:
        print(f"\nFAIL: {e}")
        return 1
    print("\nOK: Google Calendar is reachable and readable.")

    if test_book:
        if first_free is None:
            print("No free slot to test with.")
            return 1
        end = first_free + service.duration
        try:
            ev = await cal.create(first_free, end, "TEST booking (Aria setup check)",
                                  "Created by scripts/check_calendar.py, deleted right after.",
                                  "0000000000")
            print(f"OK: created test event at {first_free:%a %d %b %H:%M} ({ev.id})")
            await cal.delete(ev.id)
            print("OK: deleted the test event. Writing to the calendar works.")
        except CalendarError as e:
            print(f"\nFAIL while writing: {e}")
            print("Check the calendar is shared with the service account with "
                  "'Make changes to events'.")
            return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-book", action="store_true", help="create + delete a test event")
    sys.exit(asyncio.run(main(parser.parse_args().test_book)))
