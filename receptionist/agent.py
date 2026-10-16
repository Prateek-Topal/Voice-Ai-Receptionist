"""LiveKit voice agent: Incoming call -> STT -> LLM -> TTS -> Caller.

STT = Deepgram, LLM = Groq (with LiveKit Inference fallback), TTS = ElevenLabs.
Turn-taking is tuned in providers.build_turn_handling().
Hanging up is decided in code (call_control.py), never by the LLM.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
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


def hang_up(session: AgentSession, farewell: str) -> None:
    """Say a final line, then end the call once it has finished playing."""
    if getattr(session, "_receptionist_hanging_up", False):
        return
    session._receptionist_hanging_up = True

    async def _run() -> None:
        handle = session.say(farewell, allow_interruptions=False)
        await handle
        session.shutdown()

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class Receptionist(Agent):
    def __init__(self) -> None:
        # Tools: check_availability + book_appointment (below). No end-call tool:
        # the LLM can't hang up, on_user_turn_completed decides that.
        super().__init__(instructions=persona.instructions(BOOKING_CAPABILITIES))

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
        result = await scheduler.check_availability(date, service, preferred_time)
        logger.info("TOOL result: %s", result)
        return result

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
        said = last_user_text(context.session.history.items)
        if not is_affirmative(said):
            logger.info("TOOL book_appointment BLOCKED: caller hasn't confirmed (last: %r)", said)
            return (
                "NOT BOOKED: the caller has not confirmed yet. Read back the service, day, "
                "time, name and phone number, and ask if it's correct."
            )
        logger.info("TOOL book_appointment(%s, %s, %s, %s %s)", name, phone, service, date, time)
        result = await scheduler.book(name, phone, service, date, time)
        logger.info("TOOL result: %s", result)
        return result

    async def on_enter(self) -> None:
        # Fixed greeting = predictable and fast (no LLM round-trip on pickup).
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
                )


def attach_logging_and_latency(session: AgentSession, room_name: str) -> None:
    tracker = LatencyTracker()

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
        if role == "user":
            tracker.on_user_message(metrics)
        elif role == "assistant":
            interrupted = bool(getattr(item, "interrupted", False))
            marker = "  [interrupted by caller]" if interrupted else ""
            logger.info("%s: %s%s", persona.name.upper(), getattr(item, "text_content", ""), marker)
            turn = tracker.on_assistant_message(metrics, interrupted=interrupted)
            if turn:
                logger.info("LATENCY %s", turn.describe())

    @session.on("close")
    def _on_close(ev) -> None:
        summary = tracker.summary()
        logger.info("call ended (reason=%s)", getattr(ev, "reason", "unknown"))
        logger.info("LATENCY SUMMARY %s", summary)
        _save_latency(room_name, summary, tracker.to_records())


def _save_latency(room_name: str, summary: dict, turns: list[dict]) -> None:
    """Append one line per call to logs/latency.jsonl (used for Day 6 metrics)."""
    try:
        LOG_DIR.mkdir(exist_ok=True)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "room": room_name,
            "stt": settings.stt_provider,
            "llm": settings.groq_model if settings.llm_provider == "groq" else settings.llm_model,
            "tts": (
                settings.elevenlabs_model
                if settings.tts_provider == "elevenlabs"
                else settings.tts_model
            ),
            "endpointing": [settings.min_endpointing_delay, settings.max_endpointing_delay],
            "summary": summary,
            "turns": turns,
        }
        with Path(LOG_DIR / "latency.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:
        logger.warning("could not save latency log: %s", e)


server = AgentServer()


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("incoming session in room %s", ctx.room.name)

    session = build_session()
    attach_logging_and_latency(session, ctx.room.name)
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

    await session.start(agent=Receptionist(), room=ctx.room)
    await ctx.connect()
