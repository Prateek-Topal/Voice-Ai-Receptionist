"""Run the automated conversation tests against the real LLM.

  python scripts/run_evals.py                 all scenarios
  python scripts/run_evals.py --only cancel   one scenario (name or category)
  python scripts/run_evals.py --list          list scenarios
  python scripts/run_evals.py --show          print every transcript, not just failures

Uses an in-memory calendar (your Google Calendar is never touched) and costs LLM tokens.
On Groq's free tier, keep the default delay between scenarios to avoid rate limits.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from receptionist.agent import Receptionist  # noqa: E402
from receptionist.calendar_client import MemoryCalendar  # noqa: E402
from receptionist.config import load_settings  # noqa: E402
from receptionist.evals import SCENARIOS, run_scenario  # noqa: E402
from receptionist.persona import Persona  # noqa: E402
from receptionist.providers import build_llm  # noqa: E402
from receptionist.scheduler import Scheduler, build_rules, services_from_config  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("receptionist").setLevel(logging.WARNING)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="scenario name or category")
    ap.add_argument("--delay", type=float, default=20, help="seconds between scenarios")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--show", action="store_true", help="print all transcripts")
    ap.add_argument("--repeat", type=int, default=1,
                    help="run each scenario N times (LLMs vary; gives an honest pass rate)")
    args = ap.parse_args()

    chosen = [s for s in SCENARIOS if not args.only or args.only in (s.name, s.category)]
    chosen = chosen * max(1, args.repeat)
    if args.list or not chosen:
        for s in SCENARIOS:
            print(f"  {s.name:<22} {s.category:<12} {s.description}")
        return 0 if args.list else 1

    settings = load_settings()
    persona = Persona.from_yaml(settings.business_config_path)

    def make_scheduler() -> Scheduler:
        rules = build_rules(persona.hours, persona.timezone, settings.slot_minutes,
                            settings.min_notice_minutes, settings.booking_horizon_days)
        return Scheduler(MemoryCalendar(), rules, services_from_config(persona.services),
                         persona.business["name"],
                         phone_digits=int(persona.receptionist.get("phone_digits", 10)))

    model = settings.groq_model if settings.llm_provider == "groq" else settings.llm_model
    print(f"Running {len(chosen)} conversation(s) with {model} "
          f"({args.delay:.0f}s pause between them)\n")

    async def run_all():
        results = []
        for i, sc in enumerate(chosen):
            if i:
                await asyncio.sleep(args.delay)
            r = await run_scenario(sc, build_llm(settings), make_scheduler,
                                   lambda sch: Receptionist(sch, greet=False))
            mark = "PASS" if r.passed else "FAIL"
            print(f"  [{mark}] {r.name:<22} {r.seconds:>5.1f}s  {r.reason}")
            if r.error:
                print(f"         error: {r.error}")
            if args.show or not r.passed:
                for line in r.transcript:
                    print(f"         {line}")
                print()
            results.append(r)
        return results

    results = asyncio.run(run_all())
    passed = sum(r.passed for r in results)
    rate = 100 * passed / len(results)
    print(f"\n{passed}/{len(results)} passed ({rate:.0f}% task completion)")

    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r.passed)
    for cat, oks in by_cat.items():
        print(f"  {cat:<12} {sum(oks)}/{len(oks)}")

    (ROOT / "logs").mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "passed": passed,
        "total": len(results),
        "results": [
            {k: getattr(r, k) for k in ("name", "category", "passed", "reason", "seconds", "error")}
            for r in results
        ],
    }
    with (ROOT / "logs" / "evals.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    print("\nSaved to logs/evals.jsonl")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    start = time.perf_counter()
    code = main()
    print(f"Total time {time.perf_counter() - start:.0f}s")
    sys.exit(code)
