# Resume entry

Replace every `[ ]` with your real numbers from `docs/metrics.md`. Use only numbers you measured.

**AI Voice Receptionist** · Python, LiveKit Agents, Deepgram, Groq (gpt-oss-120b), ElevenLabs, Google Calendar API
[GitHub](https://github.com/<you>/<repo>) · [Live demo](<vercel-url>) · [Video](<youtube-url>)

- Built a real-time voice agent that answers phone and web calls, understands requests, and
  **books, cancels and reschedules appointments in Google Calendar** during the call
  (STT → LLM with tool calling → TTS on LiveKit, deployed to LiveKit Cloud).
- Achieved **[p50] s median response latency** (p95 [ ] s) by tuning endpointing and interruption
  handling, adding an LLM fallback for rate limits, and measuring every turn by stage
  (endpointing / LLM / TTS).
- Reached **[ ]% task completion** across **[ ] automated conversations**: an eval suite of
  scripted callers that runs the real agent and checks the calendar outcome, plus [ ] unit tests.
- Made bookings reliable by validating every LLM tool call in code: opening hours, double-booking
  locks, phone-number checks, and confirmation guards. The LLM proposes; deterministic code
  decides.

**Short version (one line):** Real-time AI voice receptionist (LiveKit, Deepgram, Groq,
ElevenLabs) that books appointments in Google Calendar; [p50] s median latency, [ ]% task
completion over [ ] automated test conversations.

## Talking points for interviews

- **Why the LLM can't hang up or book on its own:** small models called the end-call tool after
  the caller said their name, and once invented a phone number. Moving those decisions into
  code (goodbye detection, "yes" guard, one-question-per-turn limiter) fixed whole classes of bugs.
- **Latency budget:** where the time goes and which knob moves which number.
- **Rate limits:** Groq's free tier caused silent turns; a fallback adapter fixed it.
- **Evaluating an LLM system:** outcome-based evals (calendar state), repeated runs because LLMs
  are non-deterministic, and real-call outcome tracking.
