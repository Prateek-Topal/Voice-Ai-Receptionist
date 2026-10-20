"""Build the metrics report from your calls and eval runs.

  python scripts/metrics_report.py            print the summary and write docs/metrics.md
  python scripts/metrics_report.py --failed   also print transcripts of failed calls
  python scripts/metrics_report.py --since 2026-10-14

Reads logs/calls.jsonl (every call, written by the agent) and logs/evals.jsonl
(written by run_evals.py). Calls from before Day 6 only have latency numbers
(logs/latency.jsonl); those are included in the latency section only.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from receptionist.metrics import (  # noqa: E402
    call_stats,
    eval_stats,
    latency_stats,
    read_jsonl,
    render_markdown,
)

LOGS = ROOT / "logs"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--failed", action="store_true", help="print failed call transcripts")
    ap.add_argument("--since", help="only include records from this date (YYYY-MM-DD)")
    ap.add_argument("--out", default=str(ROOT / "docs" / "metrics.md"))
    args = ap.parse_args()

    calls = read_jsonl(LOGS / "calls.jsonl")
    runs = read_jsonl(LOGS / "evals.jsonl")
    # Pre-Day-6 latency-only records (same turn format since Day 3).
    legacy = [
        {"latency_turns": r.get("turns", []), "legacy": True}
        for r in read_jsonl(LOGS / "latency.jsonl")
        if r.get("turns") and "e2e" in r["turns"][0]
    ]
    if args.since:
        calls = [c for c in calls if c.get("timestamp", "") >= args.since]
        runs = [r for r in runs if r.get("timestamp", "") >= args.since]
        legacy = []

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = render_markdown(calls, runs, generated, latency_only=legacy)
    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")

    lat = latency_stats(calls + legacy)
    cs = call_stats(calls)
    ev = eval_stats(runs)
    print("=" * 60)
    print(" Voice AI Receptionist — metrics")
    print("=" * 60)
    if lat.get("turns"):
        print(f" Response latency   p50 {lat['p50_s']}s   p95 {lat['p95_s']}s   "
              f"avg {lat['avg_s']}s   ({lat['turns']} turns)")
        print(f"   under 1s {lat['under_1s_pct']}%   under 1.5s {lat['under_1_5s_pct']}%   "
              f"under 2s {lat['under_2s_pct']}%")
        print(f"   breakdown: endpointing {lat['avg_endpointing_s']}s + LLM "
              f"{lat['avg_llm_ttft_s']}s + TTS {lat['avg_tts_ttfb_s']}s")
    else:
        print(" Response latency   no calls yet")
    if cs.get("calls"):
        print(f" Calls              {cs['calls']} total, {cs['success_rate_pct']}% successful")
        tc = cs["task_completion_pct"]
        print(f" Task completion    {tc if tc is not None else '–'}% of calls that wanted "
              "something done")
        print(f" Bookings           {cs['successful_bookings']} booked, {cs['cancellations']} "
              f"cancelled, {cs['reschedules']} moved")
        print(f" Failed calls       {cs['failed_calls']}")
        for reason, n in cs["failure_reasons"].items():
            print(f"   {n} x {reason}")
    else:
        print(" Calls              none recorded yet (make calls with python main.py console)")
    if ev.get("runs"):
        print(f" Evals              {ev['pass_rate_pct']}% passed over {ev['attempts']} "
              f"conversations ({ev['runs']} runs)")
    else:
        print(" Evals              none yet (python scripts/run_evals.py)")
    print(f"\nFull report: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")

    if args.failed:
        for c in calls:
            if not c.get("success"):
                print(f"\n--- {c['timestamp']}  {c['outcome']}: {c['reason']}")
                for line in c.get("transcript", []):
                    print(f"   {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
