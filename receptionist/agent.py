"""LiveKit voice agent: Incoming call -> STT -> LLM -> TTS -> Caller.

Day 1: pipeline runs on LiveKit Inference so it works with only LiveKit credentials.
Day 2/3 replace the model objects in `build_session()`; nothing else changes.
"""

from __future__ import annotations

import logging

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, inference

from receptionist.config import load_settings
from receptionist.persona import Persona

settings = load_settings()
logger = logging.getLogger("receptionist")
logger.setLevel(settings.log_level)

persona = Persona.from_yaml(settings.business_config_path)

# What the agent is allowed to promise. This list grows as tools are added (Day 4).
CAPABILITIES = [
    "Answer questions about the business using only the information above.",
    "You cannot check the calendar or book appointments yet. Collect the caller's name, "
    "service, preferred date and time, and phone number, then tell them the team will "
    "call back to confirm.",
]


class Receptionist(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=persona.instructions(CAPABILITIES))

    async def on_enter(self) -> None:
        # Fixed greeting = predictable and fast (no LLM round-trip on pickup).
        self.session.say(persona.greeting)


def build_session() -> AgentSession:
    return AgentSession(
        stt=inference.STT(model=settings.stt_model, language=settings.stt_language),
        llm=inference.LLM(model=settings.llm_model),
        tts=inference.TTS(model=settings.tts_model, voice=settings.tts_voice),
    )


def attach_event_logging(session: AgentSession) -> None:
    """Log the conversation so we can see the pipeline working (and debug it)."""

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
        if getattr(item, "role", None) == "assistant":
            logger.info("%s: %s", persona.name.upper(), getattr(item, "text_content", ""))

    @session.on("close")
    def _on_close(ev) -> None:
        logger.info("call ended (reason=%s)", getattr(ev, "reason", "unknown"))


server = AgentServer()


@server.rtc_session(agent_name=settings.agent_name)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("incoming session in room %s", ctx.room.name)

    session = build_session()
    attach_event_logging(session)

    await session.start(agent=Receptionist(), room=ctx.room)
    await ctx.connect()
