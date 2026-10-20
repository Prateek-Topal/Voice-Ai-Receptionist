from types import SimpleNamespace

import pytest

from receptionist.call_control import caller_is_done, last_agent_text

ANYTHING_ELSE = "A team member will call you back. Is there anything else I can help with?"
CONFIRM = "Your number is nine eight seven... Is that correct?"


@pytest.mark.parametrize("text", ["Bye.", "Nothing. Bye.", "ok goodbye", "Have a good day!"])
def test_strong_goodbyes_always_end(text):
    assert caller_is_done(text, CONFIRM)


@pytest.mark.parametrize(
    "text", ["Nothing.", "No, thanks.", "That's all, thank you", "No, that's it."]
)
def test_weak_closers_end_after_anything_else(text):
    assert caller_is_done(text, ANYTHING_ELSE)


@pytest.mark.parametrize("text", ["Yes, that's it.", "No.", "That's all."])
def test_weak_closers_do_not_end_during_confirmation(text):
    assert not caller_is_done(text, CONFIRM)


@pytest.mark.parametrize(
    "text",
    [
        "I have a I'm having a tooth pain. On my right side of my jaw.",
        "That's the root canal.",
        "It is Rajendra Prasad.",
        "one one two two three three",
        "Yeah.",
        "Thank you.",
        "I'll drop by tomorrow",  # "by" is not "bye"
        "",
    ],
)
def test_normal_answers_never_end(text):
    assert not caller_is_done(text, ANYTHING_ELSE if text == "Yeah." else CONFIRM)


def test_last_agent_text_skips_tool_calls_and_user():
    msg = lambda r, t: SimpleNamespace(type="message", role=r, text_content=t)  # noqa: E731
    items = [msg("assistant", "Anything else?"), msg("user", "No"), SimpleNamespace(type="x")]
    assert last_agent_text(items) == "Anything else?"


@pytest.mark.parametrize("text", ["No. My", "No, my tooth also hurts", "Nothing, but can I ask"])
def test_closer_followed_by_more_speech_does_not_end(text):
    assert not caller_is_done(text, ANYTHING_ELSE)


@pytest.mark.parametrize(
    "text", ["Yes.", "Yeah, book it", "Correct", "That's right", "Okay go ahead"]
)
def test_affirmative(text):
    from receptionist.call_control import is_affirmative

    assert is_affirmative(text)


@pytest.mark.parametrize("text", ["No, that's not right", "My name is Rakesh", "Wait", ""])
def test_not_affirmative(text):
    from receptionist.call_control import is_affirmative

    assert not is_affirmative(text)


@pytest.mark.parametrize("text", ["Yes, cancel it.", "Please cancel it", "Go ahead and move it"])
def test_affirmative_for_changes(text):
    from receptionist.call_control import is_affirmative

    assert is_affirmative(text)
