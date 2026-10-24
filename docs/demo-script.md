# Demo video script (2–3 minutes)

**Goal:** in under 3 minutes, a recruiter sees Aria answer, understand, book, handle a
problem, change a booking, and that it's engineered properly (tests + metrics).

## Setup (before recording)

- Record with **OBS Studio** (free) or **Win + Alt + R** (Xbox Game Bar), 1080p.
- Use **headphones** so Aria doesn't hear herself. Turn off notifications.
- Screen layout: web demo (or terminal) on the left, **Google Calendar** (week view, the
  "Sunrise Dental – Appointments" calendar) on the right.
- In Google Calendar, create one event in advance at the time you'll ask for in scene 2,
  so Aria has to offer alternatives.
- Rehearse each call once. Keep the takes short; you can cut between scenes.

## Scenes

| Time | Scene | What to say / show |
|---|---|---|
| 0:00–0:12 | **Hook** | Voice-over on the title slide: *"Small clinics miss calls all day. This is Aria, an AI receptionist that answers, books and reschedules appointments in real time."* |
| 0:12–1:05 | **Booking + taken slot** | Call Aria: *"I'd like a teeth cleaning on Thursday at 11."* She says 11 is taken and offers the nearest times. Pick one, give name and number, confirm. **The event appears in Google Calendar on screen.** |
| 1:05–1:20 | **Interruption** | While she's listing options, cut in: *"Actually, just the earliest one."* She stops immediately and adapts. |
| 1:20–1:50 | **Reschedule** | New call: *"I need to move my appointment."* Number → new time → yes. **The event moves in the calendar.** |
| 1:50–2:20 | **Engineering** | Show the terminal: `pytest` (all green) and `run_evals.py` results, then `docs/metrics.md`: p50 latency, task completion %, bookings. |
| 2:20–2:45 | **Architecture** | The architecture diagram from the README. One sentence each: LiveKit, Deepgram, Groq, ElevenLabs, Google Calendar, *"the LLM proposes, the code validates every booking."* |
| 2:45–3:00 | **Close** | *"Code, metrics and a live demo are on GitHub"* + the repo URL. |

## After recording

- Trim dead air (Clipchamp, free on Windows, is enough).
- Add captions; many people watch muted.
- Upload to **YouTube (Unlisted)** or Loom, and put the link at the top of the README.
