# Voice test scenarios

Run `python main.py console` and speak each scenario as a fresh call (Ctrl+C and restart between calls).
After each call, note the `LATENCY SUMMARY` line from the terminal.

| # | Scenario | What you say | Aria should… |
|---|---|---|---|
| 1 | Happy-path booking | "I'd like a teeth cleaning next Tuesday at 11 AM." Then give name and number when asked. | Ask one detail at a time, say the **actual date** of next Tuesday, read the number back digit by digit, confirm everything. |
| 2 | Closed day / hours | "Can I come in on Sunday?" | Say the clinic is closed Sundays and offer another day. Never invent a slot. |
| 3 | Vague request | "Yeah I need to see someone." | Ask what the visit is for, then list the services in plain speech. |
| 4 | Info question | "What time do you close on Saturday, and where are you located?" | Answer both from `business.yaml`, briefly. |
| 5 | Mumbled / unclear | Mumble or speak a half sentence, then pause. | Ask you to repeat politely, not guess. |
| 6 | Off-topic / advice | "Which painkiller should I take for my tooth?" | Decline medical advice, offer an appointment or a call back. |

## Results

| Date | # | Pass? | Avg latency | Max latency | Notes |
|---|---|---|---|---|---|
| | 1 | | | | |
| | 2 | | | | |
| | 3 | | | | |
| | 4 | | | | |
| | 5 | | | | |
| | 6 | | | | |
