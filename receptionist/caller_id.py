"""Caller ID for phone calls.

When someone calls the phone number, LiveKit's SIP participant carries the caller's
number in the `sip.phoneNumber` attribute. Aria can then offer "Shall I use the number
you're calling from?" instead of making the caller read out every digit.
"""

from __future__ import annotations

from receptionist.scheduling import SchedulingError, normalize_phone

SIP_PHONE_ATTRIBUTE = "sip.phoneNumber"


def caller_number(attributes: dict | None, digits: int = 10) -> str | None:
    """The caller's number normalised to `digits` digits, or None if unknown/unusable."""
    raw = (attributes or {}).get(SIP_PHONE_ATTRIBUTE, "")
    if not raw:
        return None
    try:
        return normalize_phone(raw, digits)
    except SchedulingError:
        return None  # e.g. an international number with a different length


def caller_id_capability(number: str) -> str:
    return (
        f"This caller is phoning from {number}. When you need their phone number, first ask "
        f"\"Shall I use the number you're calling from, ending in {' '.join(number[-4:])}?\" "
        f"If they say yes, use {number} in the tools. Never read the full number aloud unless "
        "they ask."
    )
