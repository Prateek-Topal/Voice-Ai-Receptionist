"""Turn logs/calls.jsonl + logs/evals.jsonl into numbers and a markdown report.

Pure Python, unit-tested. Used by scripts/metrics_report.py.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # skip a half-written line
    return rows


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0-100)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.mean(vals), 2) if vals else None


# ---------------------------------------------------------------- latency


def latency_stats(calls: list[dict]) -> dict:
    """Pool every agent turn from every call."""
    turns = [t for c in calls for t in c.get("latency_turns", [])]
    totals = [t["e2e"] for t in turns if t.get("e2e") is not None]
    if not totals:
        return {"turns": 0}
    return {
        "turns": len(totals),
        "avg_s": _avg(totals),
        "p50_s": round(percentile(totals, 50), 2),
        "p90_s": round(percentile(totals, 90), 2),
        "p95_s": round(percentile(totals, 95), 2),
        "max_s": round(max(totals), 2),
        "under_1s_pct": round(100 * sum(t < 1.0 for t in totals) / len(totals)),
        "under_1_5s_pct": round(100 * sum(t < 1.5 for t in totals) / len(totals)),
        "under_2s_pct": round(100 * sum(t < 2.0 for t in totals) / len(totals)),
        "avg_endpointing_s": _avg([t.get("end_of_turn") for t in turns]),
        "avg_llm_ttft_s": _avg([t.get("llm_ttft") for t in turns]),
        "avg_tts_ttfb_s": _avg([t.get("tts_ttfb") for t in turns]),
    }


# ---------------------------------------------------------------- calls


def call_stats(calls: list[dict]) -> dict:
    if not calls:
        return {"calls": 0}
    outcomes = Counter(c.get("outcome", "unknown") for c in calls)
    # Calls where the caller tried to book / cancel / move something (a booking tool was used).
    with_intent = [
        c for c in calls
        if c.get("had_intent", c.get("outcome") in ("booked", "cancelled", "rescheduled",
                                                     "incomplete"))
    ]
    completed = sum(c.get("outcome") in ("booked", "cancelled", "rescheduled") for c in calls)
    failed = [c for c in calls if not c.get("success")]
    return {
        "calls": len(calls),
        "outcomes": dict(outcomes),
        "success_rate_pct": round(100 * sum(bool(c.get("success")) for c in calls) / len(calls)),
        # Of the calls where the caller wanted something done, how many got it done?
        "task_completion_pct": round(100 * completed / len(with_intent)) if with_intent else None,
        "successful_bookings": outcomes.get("booked", 0),
        "cancellations": outcomes.get("cancelled", 0),
        "reschedules": outcomes.get("rescheduled", 0),
        "failed_calls": len(failed),
        "failure_reasons": dict(Counter(c.get("reason", "?") for c in failed)),
        "avg_call_duration_s": _avg([c.get("duration_s") for c in calls]),
        "interruptions": sum(c.get("latency", {}).get("interruptions", 0) for c in calls),
    }


# ---------------------------------------------------------------- evals


def eval_stats(runs: list[dict]) -> dict:
    if not runs:
        return {"runs": 0}
    per_scenario: dict[str, list[bool]] = defaultdict(list)
    category: dict[str, str] = {}
    for run in runs:
        for r in run.get("results", []):
            per_scenario[r["name"]].append(bool(r["passed"]))
            category[r["name"]] = r.get("category", "")
    attempts = sum(len(v) for v in per_scenario.values())
    passes = sum(sum(v) for v in per_scenario.values())
    latest = runs[-1]
    return {
        "runs": len(runs),
        "attempts": attempts,
        "pass_rate_pct": round(100 * passes / attempts) if attempts else None,
        "latest": {
            "timestamp": latest.get("timestamp"),
            "model": latest.get("model"),
            "passed": latest.get("passed"),
            "total": latest.get("total"),
        },
        "scenarios": {
            name: {
                "category": category[name],
                "passed": sum(v),
                "attempts": len(v),
                "pass_rate_pct": round(100 * sum(v) / len(v)),
            }
            for name, v in sorted(per_scenario.items())
        },
    }


# ---------------------------------------------------------------- report


def _fmt(v, unit: str = "") -> str:
    return "–" if v is None else f"{v}{unit}"


def render_markdown(
    calls: list[dict], runs: list[dict], generated: str, latency_only: list[dict] | None = None
) -> str:
    """latency_only: older records that have per-turn latency but no outcome (pre-Day 6)."""
    lat = latency_stats(calls + (latency_only or []))
    cs, ev = call_stats(calls), eval_stats(runs)
    out = [
        f"# Metrics\n\n_Generated {generated} from `logs/calls.jsonl` and `logs/evals.jsonl`._\n"
    ]

    out.append("## Headline\n")
    out.append("| Metric | Value |\n|---|---|")
    p50 = _fmt(lat.get("p50_s"), "s")
    out.append(f"| Median response latency (caller stops → Aria speaks) | {p50} |")
    out.append(f"| p95 response latency | {_fmt(lat.get('p95_s'), 's')} |")
    out.append(f"| Task completion — automated evals | {_fmt(ev.get('pass_rate_pct'), '%')} "
               f"({ev.get('attempts', 0)} scripted conversations) |")
    out.append(f"| Task completion — real calls | {_fmt(cs.get('task_completion_pct'), '%')} |")
    out.append(f"| Successful bookings | {cs.get('successful_bookings', 0)} |")
    failed, total = cs.get("failed_calls", 0), cs.get("calls", 0)
    out.append(f"| Failed conversations | {failed} of {total} calls |")
    out.append("")

    out.append("## Response latency\n")
    if lat.get("turns"):
        out.append(f"Across **{lat['turns']} agent turns**:\n")
        out.append("| avg | p50 | p90 | p95 | max | < 1 s | < 1.5 s | < 2 s |")
        out.append("|---|---|---|---|---|---|---|---|")
        out.append(f"| {lat['avg_s']}s | {lat['p50_s']}s | {lat['p90_s']}s | {lat['p95_s']}s | "
                   f"{lat['max_s']}s | {lat['under_1s_pct']}% | {lat['under_1_5s_pct']}% | "
                   f"{lat['under_2s_pct']}% |\n")
        out.append("Where the time goes (average per turn):\n")
        out.append("| Endpointing (waiting to be sure the caller finished) | LLM first token "
                   "| TTS first audio |\n|---|---|---|")
        out.append(f"| {_fmt(lat['avg_endpointing_s'], 's')} | {_fmt(lat['avg_llm_ttft_s'], 's')} "
                   f"| {_fmt(lat['avg_tts_ttfb_s'], 's')} |\n")
    else:
        out.append("_No calls recorded yet. Make a few calls with `python main.py console`._\n")

    out.append("## Calls\n")
    if cs.get("calls"):
        out.append(f"**{cs['calls']} calls**, {cs['success_rate_pct']}% successful, "
                   f"average length {_fmt(cs['avg_call_duration_s'], 's')}, "
                   f"{cs['interruptions']} caller interruptions handled.\n")
        out.append("| Outcome | Calls |\n|---|---|")
        for k, v in sorted(cs["outcomes"].items(), key=lambda kv: -kv[1]):
            out.append(f"| {k} | {v} |")
        out.append("")
        if cs["failure_reasons"]:
            out.append("### Failed conversations\n")
            out.append("| Reason | Calls |\n|---|---|")
            for k, v in sorted(cs["failure_reasons"].items(), key=lambda kv: -kv[1]):
                out.append(f"| {k} | {v} |")
            out.append(
                "\nFull transcripts of failed calls: `python scripts/metrics_report.py --failed`\n"
            )
    else:
        out.append("_No calls recorded yet._\n")

    out.append("## Automated conversation tests\n")
    if ev.get("runs"):
        lt = ev["latest"]
        out.append(f"{ev['runs']} run(s), {ev['attempts']} conversations, "
                   f"**{ev['pass_rate_pct']}% passed** overall. Latest run: "
                   f"{lt['passed']}/{lt['total']} with `{lt['model']}` ({lt['timestamp']}).\n")
        out.append("| Scenario | Category | Passed | Pass rate |\n|---|---|---|---|")
        for name, s in ev["scenarios"].items():
            out.append(f"| {name} | {s['category']} | {s['passed']}/{s['attempts']} "
                       f"| {s['pass_rate_pct']}% |")
        out.append("")
    else:
        out.append("_No eval runs yet. Run `python scripts/run_evals.py`._\n")

    out.append("## How these are measured\n")
    out.append(
        "- **Response latency** is LiveKit's end-to-end time from the moment the caller stops "
        "speaking to the moment Aria's audio starts, measured per turn in real calls. It includes "
        "endpointing: the deliberate wait to be sure the caller has finished.\n"
        "- **Task completion (evals)**: scripted callers run against the real agent and LLM on an "
        "in-memory calendar; a run passes only if the calendar ends up in the right state.\n"
        "- **Task completion (real calls)**: of the calls where a caller tried to book, cancel or "
        "move an appointment, the share where the tool confirmed it (BOOKED / CANCELLED / "
        "RESCHEDULED).\n"
        "- **Failed conversation**: an error, a dead line, or a task that was started but never "
        "completed.\n"
    )
    return "\n".join(out)
