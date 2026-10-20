"""One record per call: what happened, how it ended, how fast it was.

Pure Python (no LiveKit) so the outcome rules are unit-tested.

Outcomes
  booked / cancelled / rescheduled   a task was completed (counts as success)
  info_only                          no booking intent, caller got answers (success)
  incomplete                         caller started a task (checked times / looked up a booking)
                                     but it never completed (counts as failed)
  failed                             error, dead line (silence) or crash (counts as failed)
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field

TASK_RESULTS = {"BOOKED": "booked", "CANCELLED": "cancelled", "RESCHEDULED": "rescheduled"}
INTENT_TOOLS = {
    "check_availability", "book_appointment", "find_booking",
    "cancel_appointment", "reschedule_appointment",
}
SUCCESS_OUTCOMES = {"booked", "cancelled", "rescheduled", "info_only"}

_DIGITS = re.compile(r"(?:\d[\s-]?){6,}\d")


def mask_numbers(text: str) -> str:
    """'9876543210' -> '******3210'. Keeps logs useful without storing full phone numbers."""

    def _mask(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group())
        return "*" * (len(digits) - 4) + digits[-4:]

    return _DIGITS.sub(_mask, text or "")


@dataclass
class ToolUse:
    name: str
    status: str  # first word of the result: AVAILABLE, BOOKED, NOT, ERROR, ...
    result: str


@dataclass
class CallRecord:
    room: str
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    end_reason: str = ""  # caller_goodbye | silence_timeout | caller_disconnected | error | ...
    tools: list[ToolUse] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)
    caller_turns: int = 0

    # ---------------------------------------------------------- recording

    def say(self, who: str, text: str) -> None:
        if who == "CALLER":
            self.caller_turns += 1
        self.transcript.append(f"{who}: {mask_numbers(text)}")

    def tool(self, name: str, result: str) -> None:
        status = (result or "").split(":", 1)[0].strip().upper()
        self.tools.append(ToolUse(name, status, mask_numbers(result)))
        self.transcript.append(f"  [{name}] {mask_numbers(result)}")

    def error(self, message: str) -> None:
        self.errors.append(mask_numbers(message)[:300])

    def end(self, reason: str) -> None:
        if not self.end_reason:  # first reason wins (e.g. goodbye before the session closes)
            self.end_reason = reason
        self.ended_at = self.ended_at or time.time()

    # ---------------------------------------------------------- outcome

    @property
    def completed_tasks(self) -> list[str]:
        return [TASK_RESULTS[t.status] for t in self.tools if t.status in TASK_RESULTS]

    @property
    def had_intent(self) -> bool:
        return any(t.name in INTENT_TOOLS for t in self.tools)

    def outcome(self) -> tuple[str, str]:
        """(outcome, reason). See module docstring."""
        if self.completed_tasks:
            return self.completed_tasks[-1], "task completed"
        if self.end_reason == "error" or (self.errors and not self.had_intent):
            return "failed", self.errors[-1] if self.errors else "session error"
        if self.end_reason == "silence_timeout":
            return "failed", "caller went silent and the call was ended"
        if any(t.status == "ERROR" for t in self.tools):
            return "failed", "calendar unavailable"
        if self.had_intent:
            last = self.tools[-1]
            return "incomplete", (
                f"started a task but didn't finish (last tool: {last.name} → {last.status})"
            )
        if self.caller_turns == 0:
            return "failed", "caller never spoke"
        return "info_only", "answered without a booking"

    def to_dict(self, latency_summary: dict | None = None, turns: list | None = None,
                config: dict | None = None) -> dict:
        outcome, reason = self.outcome()
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.started_at)),
            "room": self.room,
            "duration_s": round((self.ended_at or time.time()) - self.started_at, 1),
            "outcome": outcome,
            "success": outcome in SUCCESS_OUTCOMES,
            "had_intent": self.had_intent,
            "reason": reason,
            "end_reason": self.end_reason or "unknown",
            "caller_turns": self.caller_turns,
            "tools": [asdict(t) for t in self.tools],
            "errors": self.errors,
            "latency": latency_summary or {},
            "latency_turns": turns or [],
            "config": config or {},
            "transcript": self.transcript,
        }
