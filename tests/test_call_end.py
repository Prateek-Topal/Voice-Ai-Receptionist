import pytest

from receptionist.call_end import caller_wants_to_end


@pytest.mark.parametrize(
    "text",
    [
        "I'm having tooth problem with my left jaw.",
        "I'd like to book a cleaning on Friday.",
        "Thank you, what times do you have?",
        "",
    ],
)
def test_mid_conversation_does_not_end(text):
    assert not caller_wants_to_end(text, "How can I help you today?")


@pytest.mark.parametrize(
    "text",
    ["Okay, bye!", "That's all, thanks.", "No thank you, goodbye", "I’m done"],
)
def test_goodbye_ends(text):
    assert caller_wants_to_end(text)


def test_no_after_anything_else_ends():
    assert caller_wants_to_end("No, I'm good.", "Is there anything else I can help with?")


def test_no_without_anything_else_question_does_not_end():
    assert not caller_wants_to_end("No.", "Would you prefer a morning slot?")
