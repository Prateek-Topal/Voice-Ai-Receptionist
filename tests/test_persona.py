from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from receptionist.persona import Persona

CONFIG = Path(__file__).resolve().parent.parent / "config" / "business.yaml"


@pytest.fixture
def persona() -> Persona:
    return Persona.from_yaml(CONFIG)


def test_loads_business(persona):
    assert persona.name == "Aria"
    assert persona.business["name"] == "Sunrise Dental Clinic"


def test_greeting_is_filled_in(persona):
    assert "Sunrise Dental Clinic" in persona.greeting
    assert "{" not in persona.greeting


def test_instructions_have_no_unfilled_placeholders(persona):
    text = persona.instructions(["Answer questions."])
    assert "$" not in text
    assert "Sunrise Dental Clinic" in text
    assert "Teeth cleaning" in text
    assert "Sunday: closed" in text
    assert "Answer questions." in text


def test_instructions_include_todays_date(persona):
    fixed = datetime(2026, 10, 12, 9, 5, tzinfo=ZoneInfo("Asia/Kolkata"))
    text = persona.instructions(now=fixed)
    assert "Today is Monday, 12 October 2026" in text
    assert "9:05 AM" in text


def test_keyterms_include_services_and_business(persona):
    terms = persona.keyterms()
    assert "Sunrise Dental Clinic" in terms
    assert "Root canal consultation" in terms
    assert "appointment" in terms
    assert len(terms) == len(set(terms))


def test_missing_section_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("business:\n  name: X\n", encoding="utf-8")
    with pytest.raises(ValueError):
        Persona.from_yaml(bad)


def test_prompt_has_spoken_style_and_end_call(persona):
    text = persona.instructions()
    assert "hangs up automatically" in text
    assert "seven zero nine three" not in text  # no copyable example values
    assert "interrupts you" in text


def test_prompt_has_phone_digit_rule(persona):
    text = persona.instructions()
    assert "have 10 digits" in text
    assert "do NOT ask them to confirm again" in text


def test_farewell_filled_in(persona):
    assert "Sunrise Dental Clinic" in persona.farewell
    assert "{" not in persona.farewell


def test_prompt_forbids_inventing_details(persona):
    text = persona.instructions()
    assert "Never make one up" in text
    assert "seventeenth of October" not in text


def test_booking_prompt_mentions_tools(persona):
    from receptionist.persona import BOOKING_CAPABILITIES

    text = persona.instructions(BOOKING_CAPABILITIES)
    assert "check_availability" in text and "book_appointment" in text
    assert "Only after the caller clearly says yes" in text
