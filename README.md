# 📞 Voice AI Receptionist

An AI voice receptionist that answers phone calls, understands what the caller wants, talks naturally, and books appointments on Google Calendar. Built for clinics, coaching centres, dealerships, and small or one-person businesses.

> **Status:** Day 6 of 7 — Books, cancels and reschedules in Google Calendar; every call is measured (latency, outcome, failures) and reported in [`docs/metrics.md`](docs/metrics.md).

## How it works

```
Caller ──► LiveKit (call/audio) ──► Speech-to-Text ──► LLM agent ──► Tools (Google Calendar)
   ▲                                                       │
   └──────────────── Text-to-Speech ◄──────────────────────┘
```

| Layer | Tech | Day |
|---|---|---|
| Call / audio pipeline | LiveKit Agents | 1 ✅ |
| Speech-to-text | Deepgram Nova-3 | 2 ✅ |
| Reasoning | Groq (gpt-oss-120b) + LiveKit Inference fallback | 2 ✅ |
| Voice | ElevenLabs Flash v2.5 | 3 ✅ |
| Booking | Google Calendar API (service account) | 4 ✅ |

See [`docs/architecture.md`](docs/architecture.md) for the detailed diagram.

## Project structure

```
voice-ai-receptionist/
├── main.py                    # Entry point: python main.py console | dev | start
├── receptionist/
│   ├── agent.py               # LiveKit agent: session, logging, latency tracking
│   ├── providers.py           # Builds STT / LLM / TTS from .env.local
│   ├── latency.py             # Per-turn latency measurement
│   ├── config.py              # Loads .env.local settings
│   ├── persona.py             # Builds the LLM instructions from business.yaml
│   ├── prompts/receptionist.md# Persona prompt template
│   ├── scheduling.py          # Opening hours, free slots, booking rules (pure, unit-tested)
│   ├── scheduler.py           # check_availability / book logic used by the tools
│   ├── calendar_client.py     # Google Calendar + in-memory calendar
│   ├── call_control.py        # Goodbye + "yes" detection
│   ├── evals.py               # Automated conversation test scenarios
│   ├── call_record.py         # Per-call outcome + masked transcript
│   ├── metrics.py             # Aggregates calls + evals into the report
│   └── reply_guard.py         # One question per turn
├── config/business.yaml       # The business: name, hours, services, policies
├── scripts/
│   ├── check_env.py           # Pre-flight setup check
│   ├── chat.py                # Text-chat with Aria (no voice)
│   ├── check_calendar.py      # Test the Google Calendar connection
│   ├── run_evals.py           # Run the conversation test suite against the real LLM
│   ├── metrics_report.py      # Build docs/metrics.md from logs
│   └── diagnose_livekit.py    # Test LiveKit credentials
├── tests/                     # pytest unit tests
└── docs/                      # Architecture + daily progress log
```

## Setup

**Requirements:** Python 3.10–3.14 (3.12 recommended), a free [LiveKit Cloud](https://cloud.livekit.io) account, a [Deepgram](https://deepgram.com) key, a [Groq](https://console.groq.com) key, an [ElevenLabs](https://elevenlabs.io) key, and your PC clock set to sync automatically.

```bash
git clone https://github.com/<your-username>/voice-ai-receptionist.git
cd voice-ai-receptionist

python -m venv .venv
# Windows:      .venv\Scripts\activate
# mac/Linux:    source .venv/bin/activate

pip install -r requirements-dev.txt

# Windows: copy .env.example .env.local   |   mac/Linux: cp .env.example .env.local
# then paste your LiveKit, Deepgram, Groq and ElevenLabs keys into .env.local

python scripts/check_env.py
```

## Google Calendar setup

1. Google Cloud Console → new project → enable **Google Calendar API**.
2. IAM & Admin → Service Accounts → create one → Keys → Add key → JSON.
   Save it as `credentials/google-service-account.json` (ignored by git).
3. Google Calendar → create a calendar (time zone = the business's) → Settings →
   Share with specific people → add the service account email with **Make changes to events**.
4. Copy the calendar's **Calendar ID** into `GOOGLE_CALENDAR_ID` in `.env.local`.
5. `python scripts/check_calendar.py --test-book` should create and delete a test event.

No Google setup? Set `CALENDAR_PROVIDER=memory` to run with a fake in-memory calendar.

## How booking stays safe

The LLM proposes, the code decides. Every tool call is validated in Python before it touches the calendar:
no past times, no closed days, only within opening hours and the booking horizon, the service must exist and
fit before closing, the phone number must have 10 digits, the slot is re-checked under a lock right before
writing (no double-booking), and `book_appointment`, `cancel_appointment` and `reschedule_appointment` refuse to
run until the caller's last reply was a clear "yes". Bookings are found by the phone number they were made with,
so a caller can only change their own appointments.

## Conversation tests (evals)

`python scripts/run_evals.py` plays 11 scripted callers against the real agent and LLM on an
in-memory calendar, then checks the outcome (booked / cancelled / moved / correctly refused):
happy-path booking, taken slot, change of mind, incomplete request, short phone number,
no confirmation, closed day, unknown service, cancel, cancel with the wrong number, reschedule.
Results are appended to `logs/evals.jsonl`. `pytest` also runs the harness offline with a
scripted fake LLM, so the tool wiring and guards are tested without network access.

## Run

```bash
python main.py console   # talk through your laptop mic + speakers
python main.py dev       # connect to LiveKit Cloud → test in the browser Agent Console
python scripts/chat.py   # text-chat with Aria (fast prompt testing, no voice)
pytest                   # run tests
```

## Tuning turn-taking

All in `.env.local`, no code changes:

| Setting | Default | Effect |
|---|---|---|
| `MIN_ENDPOINTING_DELAY` / `MAX_ENDPOINTING_DELAY` | 0.5 / 1.5s | How long Aria waits after the caller stops talking. Lower = snappier, higher = fewer cut-offs. |
| `ENDPOINTING_MODE` | fixed | `dynamic` adapts to each caller but can drift upward after long silences. |
| `LLM_FALLBACK` | true | Switch to LiveKit Inference if Groq rate-limits or fails. |
| `PREEMPTIVE_GENERATION` | false | Start the LLM before the caller finishes. Faster, but doubles LLM requests. |
| `MIN_INTERRUPTION_DURATION` | 0.5s | Shorter sounds (coughs, "mm") don't interrupt Aria. |
| `FALSE_INTERRUPTION_TIMEOUT` | 1.5s | Aria resumes if an "interruption" was just noise. |
| `USER_AWAY_TIMEOUT` | 10s | Silence before Aria asks "are you still there?" |
| `VOICE_SPEED` / `VOICE_STABILITY` | 1.0 / 0.5 | ElevenLabs speaking rate and expressiveness. |

## Customise the business

Edit `config/business.yaml` — name, hours, services, policies, receptionist name and greeting. The persona prompt is generated from it, so no code changes are needed.

## Roadmap

- [x] Day 1 — Repo, structure, voice pipeline, persona
- [x] Day 2 — Deepgram STT + Groq LLM, latency tracking
- [x] Day 3 — ElevenLabs TTS, pauses, interruptions, silence handling, end-call
- [x] Day 4 — Google Calendar: check slots, book, confirm, alternatives for taken slots
- [x] Day 5 — Cancel, reschedule, unclear/incomplete answers, automated conversation tests
- [x] Day 6 — Metrics: latency, task completion, bookings, failed conversations
- [ ] Day 7 — Deploy, phone number, demo video

## Metrics

Every call is recorded in `logs/calls.jsonl` (phone numbers masked): per-turn latency, tools used, how the call
ended, and an outcome — `booked`, `cancelled`, `rescheduled`, `info_only`, `incomplete` or `failed` (with the reason).

```bash
python scripts/run_evals.py --repeat 3     # automated task-completion rate (33 scripted conversations)
python scripts/metrics_report.py           # writes docs/metrics.md
python scripts/metrics_report.py --failed  # + transcripts of failed calls
```

| Metric | How it's measured |
|---|---|
| Response latency (p50 / p95) | Caller stops speaking → Aria's audio starts, every turn of every real call |
| Task completion | Evals: scripted callers vs the real agent, pass only if the calendar ends in the right state. Real calls: share of booking/cancel/move attempts the tool confirmed |
| Successful bookings | Calls where `book_appointment` returned BOOKED |
| Failed conversations | Errors, dead lines, or tasks started but never completed — with transcripts for debugging |

Latest numbers: see [`docs/metrics.md`](docs/metrics.md).
