"""Builds the STT / LLM / TTS objects from settings.

Switching provider = change one line in .env.local, no code changes:
    STT_PROVIDER=deepgram | inference
    LLM_PROVIDER=groq     | inference
"""

from __future__ import annotations

import logging

from livekit.agents import inference
from livekit.plugins import deepgram, groq

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
        logger.info(
            "LLM: Groq %s (temperature %.1f)", settings.groq_model, settings.llm_temperature
        )
        return groq.LLM(model=settings.groq_model, temperature=settings.llm_temperature)

    logger.info("LLM: LiveKit Inference %s", settings.llm_model)
    return inference.LLM(model=settings.llm_model)


def build_tts(settings: Settings):
    # Day 3 replaces this with ElevenLabs.
    logger.info("TTS: LiveKit Inference %s", settings.tts_model)
    return inference.TTS(model=settings.tts_model, voice=settings.tts_voice)
