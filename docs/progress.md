# Progress log

## Day 1 — Foundation
- [x] Create GitHub repository
- [x] Project structure
- [x] Voice-agent framework (LiveKit Agents 1.8, Python 3.12)
- [x] Basic call/audio pipeline working (console mode)
- [x] README
- [x] Receptionist persona (`config/business.yaml` + `receptionist/prompts/receptionist.md`)

Notes:
- First successful end-to-end call: full booking conversation in console mode.
- Fixed: Python 3.15 unsupported → use 3.12; 401 errors were caused by the system clock being ~12h off.
- Observed: reply latency 4–15s, relative dates ("next Saturday") misread, agent can't end the call.

## Day 2 — Speech
- [x] Speech-to-text: Deepgram Nova-3 (direct) with keyterm prompting from `business.yaml`
- [x] LLM: Groq `openai/gpt-oss-20b` (direct, low reasoning effort)
- [x] Provider layer (`receptionist/providers.py`): switch providers via `.env.local`
- [x] Per-turn latency logging + `logs/latency.jsonl`
- [x] Today's date in the prompt (fixes relative dates)
- [x] Text-chat test mode (`scripts/chat.py`)
- [ ] Voice test scenarios (`docs/test-scenarios.md`) — fill in results

Latency (Day 1 → Day 2):
- Day 1 (Inference: Gemma + AssemblyAI/Deepgram): 4–15s per reply (observed)
- Day 2 (Deepgram + Groq): _fill in from LATENCY SUMMARY_

## Day 3 — Voice
- [x] Text-to-speech: ElevenLabs `eleven_flash_v2_5` (lowest-latency model), configurable voice/speed/stability
- [x] Natural speech: prompt rewritten for spoken style (contractions, varied acknowledgements, dates/times/numbers spoken naturally)
- [x] Pauses: dynamic endpointing 0.4–2.0s (was a fixed wait of up to 2.5–3s), LiveKit turn-detector model decides if the caller finished a thought
- [x] Silence: "are you still there?" after 10s, polite hang-up after 2 check-ins
- [x] Interruptions: adaptive interruption detection, ignores sounds < 0.5s, resumes after false interruptions; interruptions logged and counted
- [x] Call ending: built-in `end_call` tool (fixes the goodbye loop)
- [ ] Voice test scenarios 7–12 (`docs/test-scenarios.md`) — fill in results

First Day 3 test call — issues found and fixed:
- Groq free tier (8k tokens/min) rate-limited most replies → LLM first token 2.7–4.7s, some replies failed.
  Fix: `FallbackAdapter` (Groq → LiveKit Inference on 429), preemptive generation off (halves LLM requests).
- Model called `end_call` after the caller gave a name/number. A guard blocked it, but gpt-oss-20b still called the
  tool on almost every turn (extra LLM round-trip each time) and once produced a garbled multi-turn reply.
  Fix: removed the tool entirely. `on_user_turn_completed` checks every caller turn with `call_control.py`
  (strong goodbyes always end; "no/nothing/that's all" only after "anything else?"), says a farewell and hangs up.
- Phone number split across two turns, read back with a missing digit. Fix: prompt counts digits (10) and asks
  for the rest.
- Dynamic endpointing drifted to 2.0s after long silences, and short answers ("Yeah.") waited the full max.
  Fix: fixed endpointing 0.5–1.5s.
- Second call: avg latency 3.08s → **1.73s** (LLM 0.73s, TTS 0.18s), zero rate-limit errors.
  But gpt-oss-20b sometimes kept generating past its question and invented the caller's answers, copying the
  example date/number written in the prompt. Fixes: `reply_guard.py` cuts every reply after the first question
  (enforced in `llm_node`), prompt no longer contains copyable example values and forbids inventing details.
- "No. My…" ended the call → closers ("no", "nothing", "that's all") must now be the whole utterance.
- STT heard "Hi Aria" as "Hi Adi" and Aria called the caller Adi → prompt: don't use a name until the caller gives it.
- Worked first time: interruptions, silence check-in, ElevenLabs TTS first audio 0.18s.

Latency (Day 2 → Day 3):
- Day 2: _fill in_
- Day 3: _fill in from LATENCY SUMMARY_

## Day 4 — Tools (Google Calendar)
- [x] Google Calendar integration via service account (`calendar_client.py`), calls run off the audio thread
- [x] `check_availability` tool: real free slots from Google freebusy, opening hours, service duration, notice period
- [x] `book_appointment` tool: creates the event (name, phone, service; phone stored for Day 5 lookups)
- [x] Unavailable slots: offers the 3 nearest free times
- [x] Confirm booking: only after the tool returns BOOKED; booking blocked in code until the caller says "yes"
- [x] Guardrails in code: past/closed/out-of-hours/too-far/unknown service/short phone/double booking (93 tests)
- [x] Model switched to gpt-oss-120b for more reliable tool calling
- [ ] Voice test scenarios 13–19 — fill in results

## Day 5 — Agent reliability
- [x] Cancel: `find_booking` (by phone) → confirm → `cancel_appointment`, guarded by "yes"
- [x] Reschedule: find → check availability → confirm → `reschedule_appointment`; own slot excluded from busy time
      so moving an appointment 30 minutes later works, Google `events.patch` keeps the same event
- [x] Wrong number / no booking / several bookings on one day: clear tool results, nothing changed
- [x] Misunderstandings & incomplete info: prompt rules (ask only for what's missing, re-ask in other words,
      "did you say …?" for likely mishearings, follow the latest answer, offer a call back after two tries)
- [x] Automated conversation tests: 11 scripted scenarios run against the real agent + LLM, checking calendar
      outcomes (`scripts/run_evals.py`); harness itself tested offline with a scripted fake LLM (110 unit tests)
- [ ] Eval results: _fill in pass rate from run_evals.py_

## Day 6 — Evaluation
- [x] Every call recorded in `logs/calls.jsonl`: outcome (booked / cancelled / rescheduled / info_only /
      incomplete / failed + reason), end reason, tools and results, errors, per-turn latency, masked transcript
- [x] Response latency: p50 / p90 / p95 / max, % under 1 / 1.5 / 2 s, and the endpointing / LLM / TTS breakdown
- [x] Task completion: automated evals (`run_evals.py --repeat N` for an honest rate) + real calls
- [x] Successful bookings, cancellations, reschedules counted from tool results (not from what the LLM said)
- [x] Failed conversations listed by reason, with transcripts (`metrics_report.py --failed`)
- [x] `docs/metrics.md` generated for the README (119 unit tests)

## Day 7 — Ship
- [x] Dockerfile (LiveKit's pip template, Python 3.12, non-root, models pre-downloaded) + .dockerignore
- [x] Dependencies pinned to the tested versions (livekit-agents 1.8.6) for reproducible deploys
- [x] Google key delivered as a LiveKit file-mounted secret (`/etc/secrets/…`), found automatically
- [x] Phone: dispatch rule for inbound calls (`deploy/dispatch-rule.json`); caller ID offered from `sip.phoneNumber`
- [x] Safety for a public demo: `MAX_CALL_MINUTES` time limit, separate revocable key for the web app
- [x] Guides: `docs/deploy.md` (agent, phone, Vercel web demo), `docs/demo-script.md`, `docs/resume.md`
- [x] Final README: results, architecture diagram, design decisions, setup, testing (123 tests)
- [ ] Deployed agent URL / phone number / web demo URL / video link added to README
