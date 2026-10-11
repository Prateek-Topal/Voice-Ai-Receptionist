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
