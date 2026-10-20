"""Decides when the caller has ended the conversation. Pure Python, unit-tested.

The LLM is NOT allowed to hang up (small models call an end-call tool far too eagerly).
Instead, after every caller turn, the agent checks this rule and hangs up itself.

- Strong goodbyes ("bye", "have a good day") always end the call.
- Weak closers ("that's all", "no thanks", "nothing") only end it right after Aria asked
  "anything else?" — otherwise "yes, that's it" while confirming details would hang up.
"""

from __future__ import annotations

import re

_STRONG_GOODBYE = re.compile(
    r"\b("
    r"bye|goodbye|good bye|bye bye|see you|"
    r"have a (good|nice|great) (day|one|evening|night)|"
    r"hang up|end the call"
    r")\b",
    re.IGNORECASE,
)

_ANYTHING_ELSE = re.compile(
    r"anything else|something else|help (you )?with anything|any other questions?",
    re.IGNORECASE,
)

_CLOSER_WORDS = (
    r"no|nope|nah|nothing|not really|i'?m good|i'?m fine|all good|that'?s all|that is all|"
    r"that'?s it|that is it|nothing else|i'?m done|that'?s fine|thanks|thank you|okay|ok"
)
# The WHOLE utterance must be closers ("No, thanks.", "Nothing, that's all."), so
# "No, my tooth also hurts" or "No. My..." does not end the call.
_WEAK_CLOSER = re.compile(rf"^\W*(?:(?:{_CLOSER_WORDS})\W*)+$", re.IGNORECASE)


def caller_is_done(last_user_text: str, last_agent_text: str = "") -> bool:
    """True if the caller has clearly ended the conversation."""
    text = (last_user_text or "").strip()
    if not text:
        return False
    if _STRONG_GOODBYE.search(text):
        return True
    return bool(_ANYTHING_ELSE.search(last_agent_text or "") and _WEAK_CLOSER.fullmatch(text))


def last_agent_text(history_items) -> str:
    """Most recent thing Aria said."""
    for item in reversed(list(history_items)):
        if getattr(item, "type", None) == "message" and getattr(item, "role", None) == "assistant":
            return getattr(item, "text_content", None) or ""
    return ""


_AFFIRMATIVE = re.compile(
    r"^\W*(yes|yeah|yep|yup|ya|haan|correct|that'?s (right|correct)|right|sure|ok|okay|"
    r"go ahead|please (book|go ahead|confirm)|book it|confirm|confirmed|perfect|"
    r"absolutely|exactly|sounds good|all correct|that'?s it|do it|"
    r"(please |go ahead and )?(cancel|move|reschedule|change) it)\b",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    """True if the caller's reply starts with a clear yes ("Yes", "Yeah, book it", "Correct")."""
    return bool(_AFFIRMATIVE.match(text or ""))


def last_user_text(history_items) -> str:
    """Most recent thing the caller said."""
    for item in reversed(list(history_items)):
        if getattr(item, "type", None) == "message" and getattr(item, "role", None) == "user":
            return getattr(item, "text_content", None) or ""
    return ""
