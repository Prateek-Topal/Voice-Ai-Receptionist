# Deployment

Three pieces, in this order:

1. **The agent** runs 24/7 on LiveKit Cloud (no laptop needed).
2. **A phone number** so anyone can call Aria.
3. **A web demo** so anyone can talk to Aria from a browser.

---

## 1. Deploy the agent to LiveKit Cloud

**Before you start:** stop any local `python main.py dev` / `console` process. A local worker
registers under the same agent name and can steal calls from the deployed one.

```powershell
# Latest CLI
winget upgrade LiveKit.LiveKitCLI

# Link the CLI to your LiveKit Cloud project (opens a browser).
# If it says "session expired" instantly, check your PC clock syncs automatically.
lk cloud auth
lk project list
lk project set-default "<your-project-name>"
```

Prepare the secrets file (git-ignored):

```powershell
copy deploy\production.env.example deploy\production.env
code deploy\production.env      # paste your Deepgram, Groq, ElevenLabs keys + calendar ID
```

Create and deploy the agent from the project root:

```powershell
lk agent create --secrets-file deploy/production.env --secret-mount credentials/google-service-account.json
```

This registers the agent, writes `livekit.toml` (commit it), uploads the code (anything in
`.gitignore` / `.dockerignore` is excluded, so your keys never leave your machine except as
encrypted secrets), builds the `Dockerfile`, and starts it. The Google key file is mounted at
`/etc/secrets/google-service-account.json`; the agent finds it there automatically.

Check it's running:

```powershell
lk agent status
lk agent logs
```

Test it: LiveKit Cloud dashboard → **Agents / Agent Console** → agent name `receptionist` →
start a session and talk. Watch `lk agent logs` and your Google Calendar.

**Later changes**

| Task | Command |
|---|---|
| Deploy new code | `lk agent deploy` |
| Change a secret | `lk agent update-secrets --secrets "GROQ_MODEL=openai/gpt-oss-20b"` |
| Replace the key file | `lk agent update-secrets --secret-mount credentials/google-service-account.json` |
| List secret names | `lk agent secrets` |

---

## 2. Phone number

### Option A — LiveKit Phone Number (fastest)

LiveKit sells **US** local / toll-free numbers for **inbound** calls; no SIP provider needed.

1. Create the dispatch rule that sends every caller to Aria in their own room:
   ```powershell
   lk sip dispatch create deploy/dispatch-rule.json
   ```
2. Dashboard → **Telephony → Phone Numbers** → buy a number (check the current price there).
3. Assign the number to the **Aria inbound calls** dispatch rule.
4. Call it. From India this is an international call.

### Option B — An Indian number

LiveKit's own numbers are US-only. For a local Indian number use a SIP provider that LiveKit
documents (Twilio, Telnyx, Plivo, didlogic, …). Indian numbers usually need KYC documents and
can take a few days. Follow the provider's LiveKit guide to create an **inbound trunk**, then:

```powershell
lk sip dispatch create deploy/dispatch-rule.json --trunks "<your-trunk-id>"
```

### Caller ID

On phone calls Aria sees the caller's number (`sip.phoneNumber`) and offers *"Shall I use the
number you're calling from, ending in 3 2 1 0?"*, so callers don't have to read out 10 digits.
It's used only when it's a valid 10-digit (Indian) number, e.g. an Indian caller dialling in.

---

## 3. Web demo (browser, shareable link)

LiveKit's official React front-end, hosted free on Vercel. Keep it in a **separate repo**.

```powershell
cd C:\dev
lk app create --template agent-starter-react     # name it voice-ai-receptionist-web
cd voice-ai-receptionist-web
copy .env.example .env.local
```

In `.env.local`:

```
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=<key>
LIVEKIT_API_SECRET=<secret>
AGENT_NAME=receptionist
```

`AGENT_NAME` must match the agent name, or the page connects but nobody answers.

```powershell
pnpm install
pnpm dev          # open http://localhost:3000 and talk to Aria
```

Change the title/branding in the app config (company name "Sunrise Dental Clinic", page
title "Talk to Aria"), push it to GitHub, then on **vercel.com**: *Add New → Project → import
the repo → add the same four environment variables → Deploy*. You get a public URL.

### Protect your credits

The link lets anyone start a session, which spends your Deepgram / Groq / ElevenLabs credits.

- `MAX_CALL_MINUTES` (default 8) ends long calls politely.
- Use a **separate LiveKit API key** for the web app so you can revoke it any time.
- Share the link on your resume and with recruiters rather than posting it publicly, and take
  it down (or revoke the key) when you're not job-hunting.
- Set usage limits / alerts in each provider's dashboard where available.

---

## Notes

- Call records (`logs/calls.jsonl`) inside the cloud container are temporary and disappear on
  restart. Generate the metrics report from local test calls and eval runs.
- If you change `AGENT_NAME`, update the dispatch rule and the web app too.
