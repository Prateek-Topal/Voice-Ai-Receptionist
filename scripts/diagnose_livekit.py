"""Test LiveKit credentials outside the agent. Run: python scripts/diagnose_livekit.py"""

import asyncio
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
names = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")

print("== Windows environment (should be EMPTY) ==")
for n in names:
    print(f"{n}: {'SET -> ' + os.environ[n][:8] + '...' if n in os.environ else 'not set'}")

file_vals = dotenv_values(ROOT / ".env.local")
print("\n== .env.local ==")
bad_chars = (" ", '"', "'")
for n in names:
    v = file_vals.get(n) or ""
    has_junk = v.startswith(bad_chars) or v.endswith(bad_chars)
    print(f"{n}: {v[:12]!r}... len={len(v)} quotes/spaces={has_junk}")


async def main() -> None:
    from livekit import api

    url = file_vals["LIVEKIT_URL"].replace("wss://", "https://")
    lk = api.LiveKitAPI(url, file_vals["LIVEKIT_API_KEY"], file_vals["LIVEKIT_API_SECRET"])
    try:
        rooms = await lk.room.list_rooms(api.ListRoomsRequest())
        print(f"\nOK: credentials VALID for {url} ({len(rooms.rooms)} active rooms)")
    except Exception as e:  # noqa: BLE001
        print(f"\nFAIL: credentials REJECTED: {e}")
        print("Check: key/secret from the same project, and PC clock set to sync automatically.")
    finally:
        await lk.aclose()


asyncio.run(main())
