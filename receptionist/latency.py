"""Per-turn latency tracking.

LiveKit attaches timings to every chat message (ChatMessage.metrics):
  user message:      end_of_turn_delay   (deciding the caller finished speaking)
  assistant message: llm_node_ttft       (LLM time to first token)
                     tts_node_ttfb       (TTS time to first audio)
                     e2e_latency         (caller stops speaking -> Aria starts speaking)

e2e_latency is what the caller actually feels as silence. With preemptive generation
the LLM starts before the turn is confirmed, so e2e can be less than the parts added up.

Pure Python (no LiveKit imports) so it is unit-testable.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field


@dataclass
class TurnLatency:
    turn: int
    end_of_turn: float | None
    llm_ttft: float | None
    tts_ttfb: float | None
    e2e: float

    def describe(self) -> str:
        def fmt(v: float | None) -> str:
            return "n/a" if v is None else f"{v:.2f}s"

        return (
            f"turn {self.turn}: TOTAL {self.e2e:.2f}s  "
            f"(endpointing {fmt(self.end_of_turn)}, LLM first token {fmt(self.llm_ttft)}, "
            f"TTS first audio {fmt(self.tts_ttfb)})"
        )


@dataclass
class LatencyTracker:
    turns: list[TurnLatency] = field(default_factory=list)
    interruptions: int = 0
    _pending_end_of_turn: float | None = None

    def on_user_message(self, metrics: dict) -> None:
        self._pending_end_of_turn = metrics.get("end_of_turn_delay")

    def on_assistant_message(self, metrics: dict, interrupted: bool = False) -> TurnLatency | None:
        """Record a reply. Returns None for speech without an LLM step (e.g. the greeting)."""
        if interrupted:
            self.interruptions += 1
        ttft = metrics.get("llm_node_ttft")
        if ttft is None:
            return None
        ttfb = metrics.get("tts_node_ttfb")
        e2e = metrics.get("e2e_latency")
        if e2e is None:  # fall back to adding up the parts
            e2e = (self._pending_end_of_turn or 0.0) + ttft + (ttfb or 0.0)
        turn = TurnLatency(
            turn=len(self.turns) + 1,
            end_of_turn=self._pending_end_of_turn,
            llm_ttft=ttft,
            tts_ttfb=ttfb,
            e2e=e2e,
        )
        self.turns.append(turn)
        self._pending_end_of_turn = None
        return turn

    def summary(self) -> dict:
        if not self.turns:
            return {"turns": 0, "interruptions": self.interruptions}
        totals = [t.e2e for t in self.turns]

        def avg(values: list[float | None]) -> float | None:
            vals = [v for v in values if v is not None]
            return round(statistics.mean(vals), 2) if vals else None

        return {
            "turns": len(totals),
            "interruptions": self.interruptions,
            "avg_total_s": round(statistics.mean(totals), 2),
            "median_total_s": round(statistics.median(totals), 2),
            "max_total_s": round(max(totals), 2),
            "under_1s_pct": round(100 * sum(t < 1.0 for t in totals) / len(totals)),
            "avg_endpointing_s": avg([t.end_of_turn for t in self.turns]),
            "avg_llm_ttft_s": avg([t.llm_ttft for t in self.turns]),
            "avg_tts_ttfb_s": avg([t.tts_ttfb for t in self.turns]),
        }

    def to_records(self) -> list[dict]:
        return [asdict(t) for t in self.turns]
