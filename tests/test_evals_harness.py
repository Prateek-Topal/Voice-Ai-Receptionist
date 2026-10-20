"""Proves the eval harness + real agent + tools + guards work, using a scripted fake LLM.

No network: the "LLM" just replays a fixed script of text replies and tool calls.
"""

import asyncio
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ.setdefault("CALENDAR_PROVIDER", "memory")

from livekit.agents import llm  # noqa: E402
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS  # noqa: E402

from receptionist.calendar_client import MemoryCalendar  # noqa: E402
from receptionist.evals import PHONE, SCENARIOS, open_day, run_scenario  # noqa: E402
from receptionist.scheduler import Scheduler, build_rules, services_from_config  # noqa: E402

TZ = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 14, 11, 0, tzinfo=TZ)
HOURS = {d: "9 AM to 7 PM" for d in ("monday", "tuesday", "wednesday", "thursday", "friday")}
HOURS |= {"saturday": "10 AM to 2 PM", "sunday": "closed"}


class _Stream(llm.LLMStream):
    def __init__(self, owner, step, n, **kw):
        super().__init__(owner, **kw)
        self._step, self._n = step, n

    async def _run(self):
        if isinstance(self._step, str):
            delta = llm.ChoiceDelta(role="assistant", content=self._step)
        else:
            name, args = self._step
            call = llm.FunctionToolCall(
                name=name, arguments=json.dumps(args), call_id=f"c{self._n}"
            )
            delta = llm.ChoiceDelta(role="assistant", tool_calls=[call])
        self._event_ch.send_nowait(llm.ChatChunk(id=f"r{self._n}", delta=delta))


class ScriptedLLM(llm.LLM):
    def __init__(self, steps):
        super().__init__()
        self.steps, self.n = list(steps), 0

    def chat(self, *, chat_ctx, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **kw):
        step = self.steps[self.n] if self.n < len(self.steps) else "Okay."
        self.n += 1
        return _Stream(self, step, self.n, chat_ctx=chat_ctx, tools=tools or [],
                       conn_options=conn_options)


def make_scheduler():
    rules = build_rules(HOURS, "Asia/Kolkata", 30, 60, 30)
    services = services_from_config([{"name": "Teeth cleaning", "duration_minutes": 45}])
    return Scheduler(MemoryCalendar(), rules, services, "Sunrise Dental", clock=lambda: NOW)


def test_cancel_scenario_end_to_end_with_scripted_llm():
    from receptionist.agent import Receptionist

    d1 = open_day(make_scheduler()).isoformat()
    script = [
        "Sure. What's the phone number on the booking?",                 # turn 1
        ("find_booking", {"phone": PHONE}),                               # turn 2 -> tool
        "I found your teeth cleaning. Shall I cancel it?",                # after tool output
        ("cancel_appointment", {"phone": PHONE, "date": d1}),             # turn 3 -> tool
        "Done, it's cancelled.",                                          # after tool output
    ]
    sc = next(s for s in SCENARIOS if s.name == "cancel")
    result = asyncio.run(
        run_scenario(sc, ScriptedLLM(script), make_scheduler,
                     lambda sch: Receptionist(sch, greet=False))
    )
    text = "\n".join(result.transcript)
    assert result.error == "", result.error
    assert "find_booking" in text and "FOUND: 1" in text
    assert "CANCELLED:" in text
    assert result.passed, result.reason + "\n" + text


def test_guard_blocks_cancel_without_yes():
    """If the LLM tries to cancel before the caller says yes, the tool refuses."""
    from receptionist.agent import Receptionist
    from receptionist.evals import Scenario, _seed_mine, check_not_cancelled

    d1 = open_day(make_scheduler()).isoformat()
    sc = Scenario(
        "eager_cancel", "edge", "LLM cancels too early",
        lambda s, c: ["Cancel my appointment, the number is 98765 43210."],
        check_not_cancelled, seed=_seed_mine,
    )
    script = [("cancel_appointment", {"phone": PHONE, "date": d1}), "Shall I cancel it?"]
    result = asyncio.run(
        run_scenario(sc, ScriptedLLM(script), make_scheduler,
                     lambda sch: Receptionist(sch, greet=False))
    )
    assert "NOT CANCELLED: the caller has not confirmed" in "\n".join(result.transcript)
    assert result.passed, result.reason
