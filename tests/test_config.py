import pytest

from receptionist import config


@pytest.fixture
def clean_env(monkeypatch):
    for name in (
        "STT_PROVIDER", "LLM_PROVIDER", "TTS_PROVIDER", "ENDPOINTING_MODE",
        "MIN_ENDPOINTING_DELAY", "MAX_ENDPOINTING_DELAY", "VOICE_SPEED", "USER_AWAY_TIMEOUT",
        "LLM_FALLBACK", "PREEMPTIVE_GENERATION",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults(clean_env):
    s = config.load_settings()
    assert s.tts_provider == "elevenlabs"
    assert s.elevenlabs_model == "eleven_flash_v2_5"
    assert s.endpointing_mode == "fixed"
    assert s.llm_fallback is True
    assert s.preemptive_generation is False
    assert s.min_endpointing_delay <= s.max_endpointing_delay


def test_invalid_provider_rejected(clean_env):
    clean_env.setenv("TTS_PROVIDER", "openai")
    with pytest.raises(config.ConfigError):
        config.load_settings()


def test_out_of_range_speed_rejected(clean_env):
    clean_env.setenv("VOICE_SPEED", "3")
    with pytest.raises(config.ConfigError):
        config.load_settings()


def test_max_delay_below_min_rejected(clean_env):
    clean_env.setenv("MIN_ENDPOINTING_DELAY", "1.5")
    clean_env.setenv("MAX_ENDPOINTING_DELAY", "1.0")
    with pytest.raises(config.ConfigError):
        config.load_settings()


def test_elevenlabs_key_required(clean_env):
    s = config.load_settings()
    assert "ELEVENLABS_API_KEY" in config.required_provider_vars(s)


def test_bool_parsing(clean_env):
    clean_env.setenv("PREEMPTIVE_GENERATION", "yes")
    assert config.load_settings().preemptive_generation is True
    clean_env.setenv("PREEMPTIVE_GENERATION", "maybe")
    with pytest.raises(config.ConfigError):
        config.load_settings()
