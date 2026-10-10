# 📞 Voice AI Receptionist

An AI voice receptionist that answers phone calls, understands what the caller wants, talks naturally, and books appointments on Google Calendar. Built for clinics, coaching centres, dealerships, and small or one-person businesses.

> **Status:** Day 1 of 7 — voice pipeline running, persona defined. Booking arrives on Day 4.

## How it works

```
Caller ──► LiveKit (call/audio) ──► Speech-to-Text ──► LLM agent ──► Tools (Google Calendar)
   ▲                                                       │
   └──────────────── Text-to-Speech ◄──────────────────────┘
```

| Layer | Tech | Day |
|---|---|---|
| Call / audio pipeline | LiveKit Agents | 1 ✅ |
| Speech-to-text | Deepgram Nova-3 | 2 |
| Reasoning | LLM | 2 |
| Voice | ElevenLabs | 3 |
| Booking | Google Calendar API | 4 |

See [`docs/architecture.md`](docs/architecture.md) for the detailed diagram.

## Project structure

```
voice-ai-receptionist/
├── main.py                    # Entry point: python main.py console | dev | start
├── receptionist/
│   ├── agent.py               # LiveKit agent: session, pipeline, event logging
│   ├── config.py              # Loads .env.local settings
│   ├── persona.py             # Builds the LLM instructions from business.yaml
│   ├── prompts/receptionist.md# Persona prompt template
│   └── tools/                 # Calendar tools (Day 4)
├── config/business.yaml       # The business: name, hours, services, policies
├── scripts/check_env.py       # Pre-flight setup check
├── tests/                     # pytest unit tests
└── docs/                      # Architecture + daily progress log
```

## Setup

**Requirements:** Python 3.10+ (3.11 or 3.12 recommended), a free [LiveKit Cloud](https://cloud.livekit.io) account.

```bash
git clone https://github.com/<your-username>/voice-ai-receptionist.git
cd voice-ai-receptionist

python -m venv .venv
# Windows:      .venv\Scripts\activate
# mac/Linux:    source .venv/bin/activate

pip install -r requirements-dev.txt

# Windows: copy .env.example .env.local   |   mac/Linux: cp .env.example .env.local
# then paste your LiveKit URL, API key, and secret into .env.local

python scripts/check_env.py
```

## Run

```bash
python main.py console   # talk through your laptop mic + speakers
python main.py dev       # connect to LiveKit Cloud → test in the browser Agent Console
pytest                   # run tests
```

## Customise the business

Edit `config/business.yaml` — name, hours, services, policies, receptionist name and greeting. The persona prompt is generated from it, so no code changes are needed.

## Roadmap

- [x] Day 1 — Repo, structure, voice pipeline, persona
- [ ] Day 2 — Deepgram STT + LLM integration
- [ ] Day 3 — ElevenLabs TTS, pauses, interruptions
- [ ] Day 4 — Google Calendar: check slots, book, confirm
- [ ] Day 5 — Cancellations, rescheduling, edge cases
- [ ] Day 6 — Metrics: latency, task completion, booking success
- [ ] Day 7 — Deploy, phone number, demo video

## Metrics

_Coming on Day 6._
