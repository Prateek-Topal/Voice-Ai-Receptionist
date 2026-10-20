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

# Day 3 — voice, pauses and interruptions

| # | Scenario | What you do | Aria should… |
|---|---|---|---|
| 7 | Pause mid-number | "My number is seven zero nine three…" (pause 1 second) "…seven six seven nine nine three." | Wait for the full number, not reply after the first half. |
| 8 | Interrupt her | While she's listing services, say "Actually, just a cleaning." | Stop within about half a second and respond to "cleaning". Log shows `[interrupted by caller]`. |
| 9 | Backchannel / noise | Say "mm-hmm" or cough while she's talking. | Keep talking (or resume within ~1.5s). |
| 10 | Silent caller | After her question, stay silent for 10s, then 10s more, then 10s more. | Ask "are you still there?" twice, then say goodbye and hang up. |
| 11 | Natural ending | "That's all, thank you. Bye!" | Say one short goodbye and end the call (no goodbye loop). |
| 12 | Voice quality | Listen to a full booking call. | Natural voice, dates like "the seventeenth of October", numbers read in groups. |

## Day 3 results

| Date | # | Pass? | Notes |
|---|---|---|---|
| | 7 | | |
| | 8 | | |
| | 9 | | |
| | 10 | | |
| | 11 | | |
| | 12 | | |


# Day 4 — calendar booking

Before testing by voice: `python scripts/check_calendar.py --test-book` must print OK twice.
Keep calendar.google.com open to watch events appear.

| # | Scenario | What you say | Aria should… |
|---|---|---|---|
| 13 | Happy path | "Teeth cleaning tomorrow at 11." → name → number → "Yes" | Check, collect details, read back once, book. Event appears in Google Calendar. |
| 14 | Taken slot | Book the same time again in a new call | Say it's taken and offer the nearest 3 free times. |
| 15 | No time given | "A check-up on Friday." | Offer a few times spread across the day. |
| 16 | Closed day | "Sunday morning?" | Say the clinic is closed Sundays, offer another day. |
| 17 | Outside hours | "Saturday at 5 PM" | Saturday closes at 2 PM; offer earlier times. |
| 18 | Short number | Give 9 digits | Ask for the missing digit before booking. |
| 19 | No confirmation | At the read-back, say "wait, change the time" | Must NOT book. Log may show `book_appointment BLOCKED`. |

## Day 4 results

| Date | # | Pass? | Notes |
|---|---|---|---|
| | 13 | | |
| | 14 | | |
| | 15 | | |
| | 16 | | |
| | 17 | | |
| | 18 | | |
| | 19 | | |


# Day 5 — changes and reliability (voice)

Automated first: `python scripts/run_evals.py` (11 scenarios, text only). Then by voice:

| # | Scenario | What you say | Aria should… |
|---|---|---|---|
| 20 | Cancel | Book something, hang up, call again: "I need to cancel my appointment" → number → "Yes, cancel it" | Find it, read it back, cancel after yes. Event disappears from Google Calendar. |
| 21 | Reschedule | "I want to move my appointment" → number → new day/time → "Yes" | Check the new time, read back old → new, move after yes. Event moves in Google Calendar. |
| 22 | Wrong number | Cancel with a number that has no booking | Read the number back, say nothing was found. Nothing deleted. |
| 23 | Mumble | Mumble the service name | "Sorry, did you say …?" instead of guessing. |
| 24 | Partial info | "Book me something on Friday" | Ask only for the missing part (which service). |
| 25 | Change of mind | Pick 11, then "actually 3 PM" | Re-check 3 PM before continuing. |
