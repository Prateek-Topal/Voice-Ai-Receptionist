"""Settings loaded from .env.local (secrets + provider/model choices + turn-taking)."""

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
TTS_PROVIDERS = ("elevenlabs", "inference")
ENDPOINTING_MODES = ("fixed", "dynamic")
CALENDAR_PROVIDERS = ("google", "memory")


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
    llm_fallback: bool  # fall back to LiveKit Inference if Groq fails / rate-limits
    preemptive_generation: bool
    # text-to-speech
    tts_provider: str
    elevenlabs_voice_id: str
    elevenlabs_model: str
    voice_speed: float
    voice_stability: float
    tts_model: str  # inference fallback
    tts_voice: str  # inference fallback
    # turn-taking
    endpointing_mode: str
    min_endpointing_delay: float
    max_endpointing_delay: float
    min_interruption_duration: float
    false_interruption_timeout: float
    user_away_timeout: float
    # calendar (Day 4)
    calendar_provider: str
    google_calendar_id: str
    google_service_account_file: Path
    max_call_minutes: float
    slot_minutes: int
    min_notice_minutes: int
    booking_horizon_days: int
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
    if settings.tts_provider == "elevenlabs":
        needed.append("ELEVENLABS_API_KEY")
    if settings.calendar_provider == "google":
        needed.append("GOOGLE_CALENDAR_ID")
    return needed


def _float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as e:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from e
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}, got {value}")
    return value


SECRET_MOUNT_DIR = Path("/etc/secrets")


def _path(raw: str) -> Path:
    """Resolve a file path. On LiveKit Cloud, files uploaded with `--secret-mount` live in
    /etc/secrets/<filename>, so fall back there when the local path doesn't exist."""
    p = Path(raw.strip())
    p = p if p.is_absolute() else PROJECT_ROOT / p
    mounted = SECRET_MOUNT_DIR / p.name
    if not p.exists() and mounted.exists():
        return mounted
    return p


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def _choice(name: str, default: str, options: tuple[str, ...]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in options:
        raise ConfigError(f"{name} must be one of {options}, got {value!r}")
    return value


def load_settings() -> Settings:
    path = Path(os.getenv("BUSINESS_CONFIG", "config/business.yaml"))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise ConfigError(f"Business config not found: {path}")

    min_delay = _float("MIN_ENDPOINTING_DELAY", 0.5, 0.1, 3.0)
    max_delay = _float("MAX_ENDPOINTING_DELAY", 1.5, 0.3, 6.0)
    if max_delay < min_delay:
        raise ConfigError("MAX_ENDPOINTING_DELAY must be >= MIN_ENDPOINTING_DELAY")

    return Settings(
        agent_name=os.getenv("AGENT_NAME", "receptionist"),
        stt_provider=_choice("STT_PROVIDER", "deepgram", STT_PROVIDERS),
        deepgram_model=os.getenv("DEEPGRAM_MODEL", "nova-3"),
        deepgram_language=os.getenv("DEEPGRAM_LANGUAGE", "en"),
        stt_model=os.getenv("STT_MODEL", "deepgram/nova-3-general"),
        stt_language=os.getenv("STT_LANGUAGE", "en"),
        llm_provider=_choice("LLM_PROVIDER", "groq", LLM_PROVIDERS),
        groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        llm_temperature=_float("LLM_TEMPERATURE", 0.4, 0.0, 2.0),
        llm_model=os.getenv("LLM_MODEL", "google/gemma-4-31b-it"),
        llm_fallback=_bool("LLM_FALLBACK", True),
        preemptive_generation=_bool("PREEMPTIVE_GENERATION", False),
        tts_provider=_choice("TTS_PROVIDER", "elevenlabs", TTS_PROVIDERS),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "hpp4J3VqNfWAUOO0d1Us"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"),
        voice_speed=_float("VOICE_SPEED", 1.0, 0.7, 1.2),
        voice_stability=_float("VOICE_STABILITY", 0.5, 0.0, 1.0),
        tts_model=os.getenv("TTS_MODEL", "fishaudio/s2.1-pro"),
        tts_voice=os.getenv("TTS_VOICE", "fa4c9eb3dccc4806b382b40d61c6b10a"),
        endpointing_mode=_choice("ENDPOINTING_MODE", "fixed", ENDPOINTING_MODES),
        min_endpointing_delay=min_delay,
        max_endpointing_delay=max_delay,
        min_interruption_duration=_float("MIN_INTERRUPTION_DURATION", 0.5, 0.1, 3.0),
        false_interruption_timeout=_float("FALSE_INTERRUPTION_TIMEOUT", 1.5, 0.5, 5.0),
        user_away_timeout=_float("USER_AWAY_TIMEOUT", 10.0, 3.0, 120.0),
        calendar_provider=_choice("CALENDAR_PROVIDER", "google", CALENDAR_PROVIDERS),
        google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "").strip(),
        google_service_account_file=_path(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google-service-account.json")
        ),
        max_call_minutes=_float("MAX_CALL_MINUTES", 8, 1, 120),
        slot_minutes=int(_float("SLOT_MINUTES", 30, 5, 240)),
        min_notice_minutes=int(_float("MIN_NOTICE_MINUTES", 60, 0, 10080)),
        booking_horizon_days=int(_float("BOOKING_HORIZON_DAYS", 30, 1, 365)),
        business_config_path=path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
