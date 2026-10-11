"""Text-chat with Aria in the terminal (no voice). Fast way to test the persona + LLM.

Run:  python scripts/chat.py
Type 'quit' to exit, 'reset' to start a new conversation.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

from openai import OpenAI  # noqa: E402

from receptionist.config import load_settings  # noqa: E402
from receptionist.persona import DEFAULT_CAPABILITIES, Persona  # noqa: E402

settings = load_settings()
persona = Persona.from_yaml(settings.business_config_path)

api_key = os.getenv("GROQ_API_KEY", "")
if not api_key or "your" in api_key:
    sys.exit("GROQ_API_KEY is not set in .env.local")

client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
model = settings.groq_model
extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}


def new_conversation() -> list[dict]:
    return [
        {"role": "system", "content": persona.instructions(DEFAULT_CAPABILITIES)},
        {"role": "assistant", "content": persona.greeting},
    ]


def main() -> None:
    messages = new_conversation()
    print(f"Chatting with {persona.name} via Groq {model}. Type 'quit' or 'reset'.\n")
    print(f"{persona.name.upper()}: {persona.greeting}")
    ttfts: list[float] = []

    while True:
        try:
            text = input("\nYOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.lower() == "quit":
            break
        if text.lower() == "reset":
            messages = new_conversation()
            print(f"\n--- new call ---\n{persona.name.upper()}: {persona.greeting}")
            continue

        messages.append({"role": "user", "content": text})
        start = time.perf_counter()
        first_token = None
        reply = ""
        print(f"{persona.name.upper()}: ", end="", flush=True)
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.llm_temperature,
            stream=True,
            **extra,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta and first_token is None:
                first_token = time.perf_counter() - start
            reply += delta
            print(delta, end="", flush=True)
        total = time.perf_counter() - start
        messages.append({"role": "assistant", "content": reply})
        if first_token is not None:
            ttfts.append(first_token)
        print(f"\n   [first token {first_token or 0:.2f}s · full reply {total:.2f}s]")

    if ttfts:
        avg = sum(ttfts) / len(ttfts)
        print(f"\nAverage time to first token: {avg:.2f}s over {len(ttfts)} replies")


if __name__ == "__main__":
    main()
