"""Settings loaded from .env.local (secrets + provider/model choices)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# override=True: values in .env.local always win over stale Windows env vars.
# Loaded at import time so worker sub-processes also see the variables.
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

REQUIRED_LIVEKIT_VARS = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
STT_PROVIDERS = ("deepgram", "inference")
LLM_PROVIDERS = ("groq", "inference")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    agent_name: str
    # speech-to-text
    stt_provider: str
    deepgram_model: str
    deepgram_language: str
    stt_model: str  # inference fallback
    stt_language: str  # inference fallback
    # llm
    llm_provider: str
    groq_model: str
    llm_temperature: float
    llm_model: str  # inference fallback
    # text-to-speech
    tts_model: str
    tts_voice: str
    # app
    business_config_path: Path
    log_level: str


def _is_placeholder(value: str) -> bool:
    return not value.strip() or "your" in value.lower()


def missing_vars(names: tuple[str, ...] | list[str]) -> list[str]:
    """Return env vars that are unset or still placeholders."""
    return [n for n in names if _is_placeholder(os.getenv(n, ""))]


def missing_livekit_vars() -> list[str]:
    return missing_vars(REQUIRED_LIVEKIT_VARS)


def required_provider_vars(settings: Settings) -> list[str]:
    needed = []
    if settings.stt_provider == "deepgram":
        needed.append("DEEPGRAM_API_KEY")
    if settings.llm_provider == "groq":
        needed.append("GROQ_API_KEY")
    return needed


def load_settings() -> Settings:
    path = Path(os.getenv("BUSINESS_CONFIG", "config/business.yaml"))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise ConfigError(f"Business config not found: {path}")

    stt_provider = os.getenv("STT_PROVIDER", "deepgram").strip().lower()
    llm_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if stt_provider not in STT_PROVIDERS:
        raise ConfigError(f"STT_PROVIDER must be one of {STT_PROVIDERS}, got {stt_provider!r}")
    if llm_provider not in LLM_PROVIDERS:
        raise ConfigError(f"LLM_PROVIDER must be one of {LLM_PROVIDERS}, got {llm_provider!r}")

    return Settings(
        agent_name=os.getenv("AGENT_NAME", "receptionist"),
        stt_provider=stt_provider,
        deepgram_model=os.getenv("DEEPGRAM_MODEL", "nova-3"),
        deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "en"),
        stt_model=os.getenv("STT_MODEL", "deepgram/nova-3-general"),
        stt_language=os.getenv("STT_LANGUAGE", "en"),
        llm_provider=llm_provider,
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.4")),
        llm_model=os.getenv("LLM_MODEL", "google/gemma-4-31b-it"),
        tts_model=os.getenv("TTS_MODEL", "fishaudio/s2.1-pro"),
        tts_voice=os.getenv("TTS_VOICE", "fa4c9eb3dccc4806b382b40d61c6b10a"),
        business_config_path=path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
