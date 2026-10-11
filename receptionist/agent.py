"""LiveKit voice agent: Incoming call -> STT -> LLM -> TTS -> Caller.

Day 2: STT = Deepgram (direct), LLM = Groq (direct), TTS = LiveKit Inference.
Providers are chosen in .env.local; see receptionist/providers.py.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from livekit.agents import Agent, AgentServer, AgentSession, JobContext

from receptionist.config import PROJECT_ROOT, load_settings
from receptionist.latency import LatencyTracker
from receptionist.persona import DEFAULT_CAPABILITIES, Persona
from receptionist.providers import build_llm, build_stt, build_tts

settings = load_settings()
logger = logging.getLogger("receptionist")
logger.setLevel(settings.log_level)

persona = Persona.from_yaml(settings.business_config_path)
LOG_DIR = PROJECT_ROOT / "logs"


class Receptionist(Agent):
    def __init__(self) -> None:
        # Built per call so "today's date" is always current.
        super().__init__(instructions=persona.instructions(DEFAULT_CAPABILITIES))

    async def on_enter(self) -> None:
        # Fixed greeting = predictable and fast (no LLM round-trip on pickup).
        self.session.say(persona.greeting)


def build_session() -> AgentSession:
    return AgentSession(
        stt=build_stt(settings, persona),
        llm=build_llm(settings),
        tts=build_tts(settings),
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
            logger.info("%s: %s", persona.name.upper(), getattr(item, "text_content", ""))
            turn = tracker.on_assistant_message(metrics)
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

    await session.start(agent=Receptionist(), room=ctx.room)
    await ctx.connect()
