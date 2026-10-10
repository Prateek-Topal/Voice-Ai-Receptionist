"""Settings loaded from .env.local (secrets + model choices)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Loaded at import time so worker sub-processes also see the variables.
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

REQUIRED_LIVEKIT_VARS = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    agent_name: str
    stt_model: str
    stt_language: str
    llm_model: str
    tts_model: str
    tts_voice: str
    business_config_path: Path
    log_level: str


def missing_livekit_vars() -> list[str]:
    """Return LiveKit variables that are unset or still placeholders."""
    missing = []
    for name in REQUIRED_LIVEKIT_VARS:
        value = os.getenv(name, "").strip()
        if not value or "your" in value.lower():
            missing.append(name)
    return missing


def load_settings() -> Settings:
    path = Path(os.getenv("BUSINESS_CONFIG", "config/business.yaml"))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise ConfigError(f"Business config not found: {path}")

    return Settings(
        agent_name=os.getenv("AGENT_NAME", "receptionist"),
        stt_model=os.getenv("STT_MODEL", "deepgram/nova-3-general"),
        stt_language=os.getenv("STT_LANGUAGE", "en"),
        llm_model=os.getenv("LLM_MODEL", "google/gemma-4-31b-it"),
        tts_model=os.getenv("TTS_MODEL", "fishaudio/s2.1-pro"),
        tts_voice=os.getenv("TTS_VOICE", "fa4c9eb3dccc4806b382b40d61c6b10a"),
        business_config_path=path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
