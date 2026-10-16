"""Builds the STT / LLM / TTS objects and turn-taking options from settings.

Switching provider = change one line in .env.local, no code changes:
    STT_PROVIDER=deepgram   | inference
    LLM_PROVIDER=groq       | inference
    TTS_PROVIDER=elevenlabs | inference
"""

from __future__ import annotations

import logging
import os

from livekit.agents import inference, llm

# Plugins must be imported at startup (main thread), never inside functions.
from livekit.plugins import deepgram, elevenlabs, groq

from receptionist.config import Settings
from receptionist.persona import Persona

logger = logging.getLogger("receptionist.providers")


def build_stt(settings: Settings, persona: Persona):
    if settings.stt_provider == "deepgram":
        # Keyterm prompting boosts recognition of business-specific words
        # ("root canal", the clinic name) that generic models often mishear.
        keyterms = persona.keyterms()
        logger.info(
            "STT: Deepgram %s (%s), %d keyterms",
            settings.deepgram_model,
            settings.deepgram_language,
            len(keyterms),
        )
        return deepgram.STT(
            model=settings.deepgram_model,
            language=settings.deepgram_language,
            keyterm=keyterms,
        )

    logger.info("STT: LiveKit Inference %s", settings.stt_model)
    return inference.STT(model=settings.stt_model, language=settings.stt_language)


def build_llm(settings: Settings):
    if settings.llm_provider == "groq":
        # For openai/gpt-oss-* the plugin defaults reasoning_effort to "low" (fast replies).
        primary = groq.LLM(model=settings.groq_model, temperature=settings.llm_temperature)
        if not settings.llm_fallback:
            logger.info("LLM: Groq %s (no fallback)", settings.groq_model)
            return primary
        # On a rate limit (429) or outage, switch to LiveKit Inference immediately
        # instead of retrying Groq and leaving the caller in silence.
        logger.info(
            "LLM: Groq %s, falling back to LiveKit Inference %s",
            settings.groq_model,
            settings.llm_model,
        )
        return llm.FallbackAdapter(
            [primary, inference.LLM(model=settings.llm_model)],
            attempt_timeout=5.0,
            max_retry_per_llm=0,
        )

    logger.info("LLM: LiveKit Inference %s", settings.llm_model)
    return inference.LLM(model=settings.llm_model)


def build_tts(settings: Settings):
    if settings.tts_provider == "elevenlabs":
        logger.info(
            "TTS: ElevenLabs %s, voice %s, speed %.2f",
            settings.elevenlabs_model,
            settings.elevenlabs_voice_id,
            settings.voice_speed,
        )
        return elevenlabs.TTS(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            voice_id=settings.elevenlabs_voice_id,
            model=settings.elevenlabs_model,
            voice_settings=elevenlabs.VoiceSettings(
                stability=settings.voice_stability,
                similarity_boost=0.75,
                speed=settings.voice_speed,
            ),
        )

    logger.info("TTS: LiveKit Inference %s", settings.tts_model)
    return inference.TTS(model=settings.tts_model, voice=settings.tts_voice)


def build_turn_handling(settings: Settings) -> dict:
    """When to reply (endpointing) and when to stop talking (interruptions).

    Turn detection itself is left on auto: LiveKit's turn-detector model decides
    whether the caller has *finished a thought*, and endpointing sets how long
    to wait around that decision.
    """
    logger.info(
        "Turns: endpointing %s %.1f-%.1fs, interruption >= %.1fs, resume after %.1fs, "
        "preemptive %s",
        settings.endpointing_mode,
        settings.min_endpointing_delay,
        settings.max_endpointing_delay,
        settings.min_interruption_duration,
        settings.false_interruption_timeout,
        "on" if settings.preemptive_generation else "off",
    )
    return {
        # Off by default: on Groq's free tier the extra speculative requests cause rate limits.
        "preemptive_generation": {"enabled": settings.preemptive_generation},
        "endpointing": {
            "mode": settings.endpointing_mode,
            # Wait at least this long after speech stops (turn detector says "done").
            "min_delay": settings.min_endpointing_delay,
            # Never wait longer than this, even mid-sentence pauses (e.g. reading a number).
            "max_delay": settings.max_endpointing_delay,
        },
        "interruption": {
            "enabled": True,
            # Ignore short sounds: coughs, "mm", background noise.
            "min_duration": settings.min_interruption_duration,
            # If the "interruption" was noise, pick up where Aria left off.
            "resume_false_interruption": True,
            "false_interruption_timeout": settings.false_interruption_timeout,
        },
    }


def build_scheduler(settings: Settings, persona: Persona):
    """Scheduler backed by Google Calendar, or an in-memory calendar if not configured."""
    from receptionist.calendar_client import GoogleCalendar, MemoryCalendar
    from receptionist.scheduler import Scheduler, build_rules, services_from_config

    calendar = None
    if settings.calendar_provider == "google":
        missing = []
        if not settings.google_calendar_id or "your" in settings.google_calendar_id:
            missing.append("GOOGLE_CALENDAR_ID")
        if not settings.google_service_account_file.exists():
            missing.append(f"service account file {settings.google_service_account_file}")
        if missing:
            logger.warning(
                "Calendar: Google not configured (%s). Using an IN-MEMORY calendar: bookings "
                "will NOT be saved.",
                ", ".join(missing),
            )
        else:
            logger.info("Calendar: Google Calendar %s", settings.google_calendar_id)
            calendar = GoogleCalendar(
                settings.google_calendar_id, settings.google_service_account_file, persona.timezone
            )
    if calendar is None:
        if settings.calendar_provider == "memory":
            logger.info("Calendar: in-memory (CALENDAR_PROVIDER=memory), bookings are not saved")
        calendar = MemoryCalendar()

    rules = build_rules(
        persona.hours,
        persona.timezone,
        settings.slot_minutes,
        settings.min_notice_minutes,
        settings.booking_horizon_days,
    )
    return Scheduler(
        calendar,
        rules,
        services_from_config(persona.services),
        persona.business["name"],
        phone_digits=int(persona.receptionist.get("phone_digits", 10)),
    )
