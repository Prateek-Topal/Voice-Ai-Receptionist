"""Guard against the LLM hanging up mid-conversation.

Small models sometimes call end_call on an ordinary turn ("I have a tooth problem").
We only let the hang-up through when the caller actually signalled they're done.
"""

from __future__ import annotations

import re

from livekit.agents.beta.tools import EndCallTool
from livekit.agents.voice.events import RunContext

# Phrases that mean "I'm done" anywhere in the caller's last turn.
_GOODBYE = re.compile(
    r"\b(bye|goodbye|good bye|that'?s all|that is all|that'?s it|nothing else|"
    r"no thanks|no thank you|i'?m done|i am done|all set|hang up|end the call)\b"
)
# Short replies that mean "no" when we just asked "anything else?".
_NO = re.compile(r"^(no|nope|nah|no,? i'?m good|i'?m good|that'?s fine)\b")

REFUSAL = (
    "The caller has NOT finished. Do not end the call. "
    "Continue the conversation and respond to what the caller just said."
)


def _normalize(text: str) -> str:
    return text.lower().replace("’", "'").strip()


def caller_wants_to_end(last_user: str, last_assistant: str = "") -> bool:
    user = _normalize(last_user)
    if not user:
        return False
    if _GOODBYE.search(user):
        return True
    asked_anything_else = "anything else" in _normalize(last_assistant)
    return asked_anything_else and bool(_NO.match(user))


def _last_texts(ctx: RunContext) -> tuple[str, str]:
    last_user, last_assistant = "", ""
    for item in reversed(ctx.session.history.items):
        role = getattr(item, "role", None)
        text = getattr(item, "text_content", None) or ""
        if role == "user" and not last_user:
            last_user = text
        elif role == "assistant" and last_user and not last_assistant:
            # the assistant message that came *before* the caller's last turn
            last_assistant = text
        if last_user and last_assistant:
            break
    return last_user, last_assistant


class GuardedEndCallTool(EndCallTool):
    async def _end_call(self, ctx: RunContext):
        last_user, last_assistant = _last_texts(ctx)
        if not caller_wants_to_end(last_user, last_assistant):
            return REFUSAL
        return await super()._end_call(ctx)
