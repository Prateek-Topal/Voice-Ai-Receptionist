# 📞 Voice AI Receptionist

An AI voice receptionist that answers phone calls, understands what the caller wants, talks naturally, and books appointments on Google Calendar. Built for clinics, coaching centres, dealerships, and small or one-person businesses.

> **Status:** Day 4 of 7 — Aria checks real availability and books appointments in Google Calendar during the call, with every booking validated in code.

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
│   └── reply_guard.py         # One question per turn
├── config/business.yaml       # The business: name, hours, services, policies
├── scripts/
│   ├── check_env.py           # Pre-flight setup check
│   ├── chat.py                # Text-chat with Aria (no voice)
│   ├── check_calendar.py      # Test the Google Calendar connection
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
writing (no double-booking), and `book_appointment` refuses to run until the caller's last reply was a clear "yes".

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
- [ ] Day 5 — Cancellations, rescheduling, edge cases
- [ ] Day 6 — Metrics: latency, task completion, booking success
- [ ] Day 7 — Deploy, phone number, demo video

## Metrics

Every call logs per-turn latency (`LATENCY turn N: TOTAL …`) and appends a summary to `logs/latency.jsonl`. Full metrics dashboard on Day 6.
