"""Pre-flight check. Run:  python scripts/check_env.py"""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ok = True


def check(label: str, passed: bool, hint: str = "") -> None:
    global ok
    ok &= passed
    print(f"[{'OK' if passed else 'FAIL'}] {label}" + ("" if passed else f"  ->  {hint}"))


check(
    f"Python {sys.version.split()[0]}",
    (3, 10) <= sys.version_info[:2] <= (3, 14),
    "Use Python 3.10-3.14 (3.12 recommended)",
)

for pkg in ("livekit.agents", "livekit.plugins.deepgram", "livekit.plugins.groq",
            "openai", "dotenv", "yaml", "tzdata"):
    try:
        importlib.import_module(pkg)
        check(f"package {pkg}", True)
    except ImportError:
        check(f"package {pkg}", False, "pip install -r requirements-dev.txt")

check(".env.local exists", (ROOT / ".env.local").exists(), "copy .env.example to .env.local")

from receptionist.config import (  # noqa: E402
    load_settings,
    missing_livekit_vars,
    missing_vars,
    required_provider_vars,
)
from receptionist.persona import Persona  # noqa: E402

missing = missing_livekit_vars()
check("LiveKit credentials set", not missing, f"fill in {', '.join(missing)} in .env.local")

try:
    s = load_settings()
    print(f"     STT={s.stt_provider}  LLM={s.llm_provider}"
          f" ({s.groq_model if s.llm_provider == 'groq' else s.llm_model})")
    prov_missing = missing_vars(required_provider_vars(s))
    check("provider API keys set", not prov_missing,
          f"fill in {', '.join(prov_missing)} in .env.local")
    p = Persona.from_yaml(s.business_config_path)
    p.instructions()
    check(f"persona '{p.name}' for '{p.business['name']}' (today: {p.now():%a %d %b})", True)
except Exception as e:  # noqa: BLE001
    check("settings/persona", False, str(e))

print("\nAll good — run: python main.py console" if ok else "\nFix the FAIL items above.")
sys.exit(0 if ok else 1)
