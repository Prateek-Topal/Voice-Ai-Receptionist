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
