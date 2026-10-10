# Progress log

## Day 1 — Foundation (7 Oct 2026)
- [x] Create GitHub repository
- [x] Project structure
- [x] Voice-agent framework (LiveKit Agents)
- [x] Basic call/audio pipeline working (console + browser Agent Console)
- [x] README
- [x] Receptionist persona (`config/business.yaml` + `receptionist/prompts/receptionist.md`)

Notes:
- Pipeline uses LiveKit Inference models for now; replaced with dedicated providers on Days 2–3.

Day-1:
- First successful end-to-end call: full booking conversation in console mode.
- Fixed: Python 3.15 unsupported -> use 3.12;401 errors were caused by the system clock being ~12h off.
- To fix later: reply latency 4-15s (Day 4), agent can't end the call (Day 5)