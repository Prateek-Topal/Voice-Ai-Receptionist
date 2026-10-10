"""Pre-flight check. Run:  python scripts/check_env.py"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ok = True


def check(label: str, passed: bool, hint: str = "") -> None:
    global ok
    ok &= passed
    print(f"[{'OK' if passed else 'FAIL'}] {label}" + ("" if passed else f"  ->  {hint}"))


check(
    f"Python {sys.version.split()[0]}",
    sys.version_info >= (3, 10),
    "Install Python 3.10+ (3.11/3.12 recommended)",
)

for pkg in ("livekit.agents", "dotenv", "yaml"):
    try:
        importlib.import_module(pkg)
        check(f"package {pkg}", True)
    except ImportError:
        check(f"package {pkg}", False, "pip install -r requirements-dev.txt")

root = Path(__file__).resolve().parent.parent
check(".env.local exists", (root / ".env.local").exists(), "copy .env.example to .env.local")

from receptionist.config import load_settings, missing_livekit_vars  # noqa: E402
from receptionist.persona import Persona  # noqa: E402

missing = missing_livekit_vars()
check("LiveKit credentials set", not missing, f"fill in {', '.join(missing)} in .env.local")

try:
    s = load_settings()
    p = Persona.from_yaml(s.business_config_path)
    p.instructions(["test"])
    check(f"persona '{p.name}' for '{p.business['name']}'", True)
except Exception as e:  # noqa: BLE001
    check("persona/config", False, str(e))

print("\nAll good — run: python main.py console" if ok else "\nFix the FAIL items above.")
sys.exit(0 if ok else 1)
