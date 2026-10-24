"""LiveKit voice agent: Incoming call -> STT -> LLM -> TTS -> Caller.

STT = Deepgram, LLM = Groq (with LiveKit Inference fallback), TTS = ElevenLabs.
Turn-taking is tuned in providers.build_turn_handling().
Hanging up is decided in code (call_control.py), never by the LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    StopResponse,
    function_tool,
)

from receptionist.call_control import (
    caller_is_done,
    is_affirmative,
    last_agent_text,
    last_user_text,
)
from receptionist.call_record import CallRecord
from receptionist.caller_id import caller_id_capability, caller_number
from receptionist.config import PROJECT_ROOT, load_settings
from receptionist.latency import LatencyTracker
from receptionist.persona import BOOKING_CAPABILITIES, Persona
from receptionist.providers import (
    build_llm,
    build_scheduler,
    build_stt,
    build_tts,
    build_turn_handling,
)
from receptionist.reply_guard import ReplyLimiter

settings = load_settings()
logger = logging.getLogger("receptionist")
logger.setLevel(settings.log_level)

# The ElevenLabs plugin logs raw audio at DEBUG level, which floods the console.
logging.getLogger("livekit.plugins.elevenlabs").setLevel(logging.INFO)

persona = Persona.from_yaml(settings.business_config_path)
scheduler = build_scheduler(settings, persona)
LOG_DIR = PROJECT_ROOT / "logs"

# How many "are you still there?" check-ins before hanging up on a silent line.
MAX_SILENCE_CHECKS = 2

_background_tasks: set[asyncio.Task] = set()


def hang_up(session: AgentSession, farewell: str, reason: str = "caller_goodbye") -> None:
    """Say a final line, then end the call once it has finished playing."""
    if getattr(session, "_receptionist_hanging_up", False):
        return
    session._receptionist_hanging_up = True
    record = getattr(session, "_receptionist_record", None)
    if record is not None:
        record.end(reason)

    async def _run() -> None:
        handle = session.say(farewell, allow_interruptions=False)
        await handle
        session.shutdown()

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


CONFIRM_FIRST = (
    "the caller has not confirmed yet. Read back what will change and ask if it's correct."
)


class Receptionist(Agent):
    def __init__(self, booking_scheduler=None, greet: bool = True) -> None:
        # Tools below: availability, booking, lookup, cancel, reschedule. No end-call tool:
        # the LLM can't hang up, on_user_turn_completed decides that.
        self.scheduler = booking_scheduler or scheduler
        self._greet = greet
        self.record: CallRecord | None = None  # set per call by the entrypoint
        self.caller_number: str | None = None
        super().__init__(instructions=persona.instructions(BOOKING_CAPABILITIES))

    async def use_caller_id(self, number: str) -> None:
        """Phone calls: let Aria offer the number the caller is phoning from."""
        if self.caller_number == number:
            return
        self.caller_number = number
        logger.info("caller ID: number ending %s", number[-4:])
        await self.update_instructions(
            persona.instructions(BOOKING_CAPABILITIES + [caller_id_capability(number)])
        )

    def _log_tool(self, name: str, result: str) -> str:
        logger.info("TOOL result: %s", result)
        if self.record is not None:
            self.record.tool(name, result)
        return result

    def _confirmed(self, context: RunContext, tool: str) -> bool:
        said = last_user_text(context.session.history.items)
        if is_affirmative(said):
            return True
        logger.info("TOOL %s BLOCKED: caller hasn't confirmed (last: %r)", tool, said)
        return False

    @function_tool
    async def check_availability(
        self,
        context: RunContext,
        date: str,
        service: str,
        preferred_time: str | None = None,
    ) -> str:
        """Look up free appointment times in the clinic's calendar.

        Call this as soon as you know the service and the day the caller wants.

        Args:
            date: The day in YYYY-MM-DD format, worked out from today's date.
            service: The service the caller wants, using a name from the services list.
            preferred_time: The time the caller asked for, as 24-hour HH:MM. Leave empty if
                they didn't say a time.
        """
        logger.info("TOOL check_availability(date=%s, service=%s, time=%s)",
                    date, service, preferred_time)
        result = await self.scheduler.check_availability(date, service, preferred_time)
        return self._log_tool("check_availability", result)

    @function_tool
    async def book_appointment(
        self,
        context: RunContext,
        name: str,
        phone: str,
        service: str,
        date: str,
        time: str,
    ) -> str:
        """Book the appointment in the clinic's calendar.

        Only call this after you have read all the details back to the caller and they
        clearly said yes.

        Args:
            name: The caller's full name, exactly as they said it.
            phone: The caller's phone number, digits only.
            service: The service, using a name from the services list.
            date: The day in YYYY-MM-DD format.
            time: The start time as 24-hour HH:MM, one of the free times you offered.
        """
        if not self._confirmed(context, "book_appointment"):
            return self._log_tool("book_appointment", f"NOT BOOKED: {CONFIRM_FIRST}")
        logger.info("TOOL book_appointment(%s, %s, %s, %s %s)", name, phone, service, date, time)
        result = await self.scheduler.book(name, phone, service, date, time)
        return self._log_tool("book_appointment", result)

    @function_tool
    async def find_booking(self, context: RunContext, phone: str) -> str:
        """Find the caller's upcoming appointments by the phone number they booked with.

        Args:
            phone: The phone number the appointment was booked with, digits only.
        """
        logger.info("TOOL find_booking(%s)", phone)
        result = await self.scheduler.find_bookings(phone)
        return self._log_tool("find_booking", result)

    @function_tool
    async def cancel_appointment(
        self, context: RunContext, phone: str, date: str, time: str | None = None
    ) -> str:
        """Cancel the caller's appointment.

        Only call this after find_booking, and after the caller clearly said yes to cancelling.

        Args:
            phone: The phone number the appointment was booked with, digits only.
            date: The appointment's day in YYYY-MM-DD format.
            time: The appointment's start time as 24-hour HH:MM. Needed only if they have
                more than one appointment that day.
        """
        if not self._confirmed(context, "cancel_appointment"):
            return self._log_tool("cancel_appointment", f"NOT CANCELLED: {CONFIRM_FIRST}")
        logger.info("TOOL cancel_appointment(%s, %s %s)", phone, date, time)
        result = await self.scheduler.cancel(phone, date, time)
        return self._log_tool("cancel_appointment", result)

    @function_tool
    async def reschedule_appointment(
        self,
        context: RunContext,
        phone: str,
        current_date: str,
        new_date: str,
        new_time: str,
        current_time: str | None = None,
    ) -> str:
        """Move the caller's appointment to a new day and time.

        Only call this after find_booking and check_availability, and after the caller
        clearly said yes to the change.

        Args:
            phone: The phone number the appointment was booked with, digits only.
            current_date: The day of the existing appointment, YYYY-MM-DD.
            new_date: The new day, YYYY-MM-DD.
            new_time: The new start time as 24-hour HH:MM, one of the free times you offered.
            current_time: The existing appointment's time as 24-hour HH:MM. Needed only if
                they have more than one appointment that day.
        """
        if not self._confirmed(context, "reschedule_appointment"):
            return self._log_tool(
                "reschedule_appointment", f"NOT RESCHEDULED: {CONFIRM_FIRST}"
            )
        logger.info("TOOL reschedule_appointment(%s, %s %s -> %s %s)",
                    phone, current_date, current_time, new_date, new_time)
        result = await self.scheduler.reschedule(
            phone, current_date, new_date, new_time, current_time
        )
        return self._log_tool("reschedule_appointment", result)

    async def on_enter(self) -> None:
        # Fixed greeting = predictable and fast (no LLM round-trip on pickup).
        if self._greet:
            self.session.say(persona.greeting)

    async def llm_node(self, chat_ctx, tools, model_settings):
        """Stream the LLM reply, but stop after the first question (one question per turn)."""
        limiter = ReplyLimiter()
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            if isinstance(chunk, str):
                text = chunk
            else:
                delta = getattr(chunk, "delta", None)
                if delta is None or getattr(delta, "tool_calls", None):
                    yield chunk  # tool calls etc. pass through untouched
                    continue
                text = delta.content or ""
            spoken = limiter.feed(text)
            if spoken:
                yield spoken
            if limiter.done:
                if limiter.trimmed:
                    logger.info("trimmed reply after first question (model kept talking)")
                break

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Runs after every caller turn, before the LLM. Ends the call on a goodbye."""
        user_text = getattr(new_message, "text_content", None) or ""
        if caller_is_done(user_text, last_agent_text(turn_ctx.items)):
            logger.info("caller said goodbye (%r), ending call", user_text)
            hang_up(self.session, persona.farewell)
            raise StopResponse()  # skip the LLM for this turn


def build_session() -> AgentSession:
    return AgentSession(
        stt=build_stt(settings, persona),
        llm=build_llm(settings),
        tts=build_tts(settings),
        turn_handling=build_turn_handling(settings),
        user_away_timeout=settings.user_away_timeout,
    )


def attach_silence_handling(session: AgentSession) -> None:
    """Check in when the caller goes quiet; hang up politely if the line stays dead."""
    state = {"checks": 0}

    @session.on("user_state_changed")
    def _on_user_state(ev) -> None:
        if ev.new_state == "speaking":
            state["checks"] = 0  # caller is back
        elif ev.new_state == "away":
            state["checks"] += 1
            if state["checks"] <= MAX_SILENCE_CHECKS:
                logger.info("caller silent, check-in %d/%d", state["checks"], MAX_SILENCE_CHECKS)
                session.generate_reply(
                    instructions=(
                        "The caller has gone quiet. In one short, friendly sentence, ask if "
                        "they're still there. Do not repeat your previous question word for word."
                    )
                )
            else:
                logger.info("caller still silent, ending call")
                hang_up(
                    session,
                    "It seems we've lost the connection. Please call us back anytime. Goodbye!",
                    reason="silence_timeout",
                )


def attach_call_tracking(session: AgentSession, record: CallRecord) -> None:
    """Log the conversation, measure latency per turn, and save one record per call."""
    tracker = LatencyTracker()
    session._receptionist_record = record

    @session.on("agent_state_changed")
    def _on_state(ev) -> None:
        logger.debug("agent state: %s -> %s", ev.old_state, ev.new_state)

    @session.on("user_input_transcribed")
    def _on_user(ev) -> None:
        if ev.is_final:
            logger.info("CALLER: %s", ev.transcript)

    @session.on("conversation_item_added")
    def _on_item(ev) -> None:
        item = ev.item
        role = getattr(item, "role", None)
        metrics = dict(getattr(item, "metrics", None) or {})
        text = getattr(item, "text_content", "") or ""
        if role == "user":
            record.say("CALLER", text)
            tracker.on_user_message(metrics)
        elif role == "assistant":
            interrupted = bool(getattr(item, "interrupted", False))
            marker = "  [interrupted by caller]" if interrupted else ""
            logger.info("%s: %s%s", persona.name.upper(), text, marker)
            record.say(persona.name.upper(), text + marker)
            turn = tracker.on_assistant_message(metrics, interrupted=interrupted)
            if turn:
                logger.info("LATENCY %s", turn.describe())

    @session.on("error")
    def _on_error(ev) -> None:
        err = getattr(ev, "error", None)
        recoverable = getattr(err, "recoverable", True)
        record.error(f"{type(err).__name__}: {err}"[:300])
        if not recoverable:
            record.end("error")

    @session.on("close")
    def _on_close(ev) -> None:
        if getattr(ev, "error", None):
            record.error(str(ev.error)[:300])
            record.end("error")
        reason = getattr(ev, "reason", "unknown")
        record.end(str(getattr(reason, "value", reason)))  # keeps an earlier reason if set
        summary = tracker.summary()
        data = record.to_dict(summary, tracker.to_records(), _config_snapshot())
        logger.info("call ended: %s (%s) after %.0fs", data["outcome"], data["reason"],
                    data["duration_s"])
        logger.info("LATENCY SUMMARY %s", summary)
        _save_call(data)


def _config_snapshot() -> dict:
    return {
        "stt": settings.stt_provider,
        "llm": settings.groq_model if settings.llm_provider == "groq" else settings.llm_model,
        "tts": settings.elevenlabs_model if settings.tts_provider == "elevenlabs"
        else settings.tts_model,
        "calendar": settings.calendar_provider,
        "endpointing": [settings.min_endpointing_delay, settings.max_endpointing_delay],
    }


def _save_call(data: dict) -> None:
    """Append one line per call to logs/calls.jsonl (read by scripts/metrics_report.py)."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with Path(LOG_DIR / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(data) + "\n")
    except OSError as e:
        logger.warning("could not save call record: %s", e)


server = AgentServer()


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("incoming session in room %s", ctx.room.name)

    session = build_session()
    record = CallRecord(room=ctx.room.name)
    attach_call_tracking(session, record)
    attach_silence_handling(session)

    @session.on("close")
    def _end_job(_ev) -> None:
        # Deleting the room disconnects a phone caller (SIP). No-op in console mode.
        async def _delete_room() -> None:
            try:
                await ctx.delete_room()
            except Exception as e:  # noqa: BLE001
                logger.debug("delete_room skipped: %s", e)

        ctx.add_shutdown_callback(_delete_room)
        ctx.shutdown(reason="call ended")

    agent = Receptionist()
    agent.record = record
    await session.start(agent=agent, room=ctx.room)
    await ctx.connect()
    _watch_for_caller_id(ctx, agent)
    _enforce_time_limit(session)


def _watch_for_caller_id(ctx: JobContext, agent: Receptionist) -> None:
    """Phone callers join as SIP participants carrying their number as an attribute."""
    digits = int(persona.receptionist.get("phone_digits", 10))

    def _check(participant) -> None:
        number = caller_number(getattr(participant, "attributes", None), digits)
        if number:
            task = asyncio.create_task(agent.use_caller_id(number))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

    for p in ctx.room.remote_participants.values():
        _check(p)
    ctx.room.on("participant_connected", _check)


def _enforce_time_limit(session: AgentSession) -> None:
    """End very long calls politely. Protects API credits when the demo is public."""

    async def _limit() -> None:
        await asyncio.sleep(settings.max_call_minutes * 60)
        logger.info("call reached the %.0f-minute limit, ending", settings.max_call_minutes)
        hang_up(
            session,
            "I'm sorry, we've reached the time limit for this call. Please call again if "
            "you need anything else. Goodbye!",
            reason="time_limit",
        )

    task = asyncio.create_task(_limit())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    session.on("close", lambda _ev: task.cancel())
