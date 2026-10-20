# Metrics

_Generated 2026-10-20 21:49 from `logs/calls.jsonl` and `logs/evals.jsonl`._

## Headline

| Metric | Value |
|---|---|
| Median response latency (caller stops → Aria speaks) | 2.0s |
| p95 response latency | 4.92s |
| Task completion — automated evals | 95% (44 scripted conversations) |
| Task completion — real calls | – |
| Successful bookings | 0 |
| Failed conversations | 0 of 0 calls |

## Response latency

Across **121 agent turns**:

| avg | p50 | p90 | p95 | max | < 1 s | < 1.5 s | < 2 s |
|---|---|---|---|---|---|---|---|
| 2.28s | 2.0s | 4.2s | 4.92s | 6.27s | 12% | 30% | 50% |

Where the time goes (average per turn):

| Endpointing (waiting to be sure the caller finished) | LLM first token | TTS first audio |
|---|---|---|
| 0.97s | 0.83s | 0.28s |

## Calls

_No calls recorded yet._

## Automated conversation tests

2 run(s), 44 conversations, **95% passed** overall. Latest run: 31/33 with `openai/gpt-oss-20b` (2026-10-20T20:19:17).

| Scenario | Category | Passed | Pass rate |
|---|---|---|---|
| book_happy_path | booking | 4/4 | 100% |
| cancel | change | 4/4 | 100% |
| cancel_wrong_number | change | 4/4 | 100% |
| change_of_mind | reliability | 4/4 | 100% |
| closed_day | edge | 4/4 | 100% |
| incomplete_request | reliability | 4/4 | 100% |
| no_confirmation | edge | 4/4 | 100% |
| reschedule | change | 4/4 | 100% |
| short_phone_number | edge | 4/4 | 100% |
| slot_taken | booking | 2/4 | 50% |
| unknown_service | edge | 4/4 | 100% |

## How these are measured

- **Response latency** is LiveKit's end-to-end time from the moment the caller stops speaking to the moment Aria's audio starts, measured per turn in real calls. It includes endpointing: the deliberate wait to be sure the caller has finished.
- **Task completion (evals)**: scripted callers run against the real agent and LLM on an in-memory calendar; a run passes only if the calendar ends up in the right state.
- **Task completion (real calls)**: of the calls where a caller tried to book, cancel or move an appointment, the share where the tool confirmed it (BOOKED / CANCELLED / RESCHEDULED).
- **Failed conversation**: an error, a dead line, or a task that was started but never completed.
