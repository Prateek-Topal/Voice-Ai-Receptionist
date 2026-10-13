"""Stops the LLM from rambling or talking for the caller. Pure Python, unit-tested.

Small models sometimes keep generating after their question and invent the caller's
answers ("Could you give me your number?So your number is ..."). A receptionist asks
ONE question and waits, so the reply is cut right after the first question mark.
Also caps very long replies.
"""

from __future__ import annotations

import re

MAX_SENTENCES = 4
MAX_CHARS = 320
_SENTENCE_END = re.compile(r"[.!?]")


class ReplyLimiter:
    def __init__(self, max_sentences: int = MAX_SENTENCES, max_chars: int = MAX_CHARS) -> None:
        self.max_sentences = max_sentences
        self.max_chars = max_chars
        self.text = ""
        self.done = False
        self.trimmed = False

    def feed(self, chunk: str) -> str:
        """Return the part of `chunk` that may be spoken. Sets `done` when the reply must end."""
        if self.done or not chunk:
            return ""
        start = len(self.text)
        combined = self.text + chunk

        cut = None
        q = combined.find("?", start)
        if q != -1:
            cut = q + 1  # end of the first question
        else:
            ends = [m.end() for m in _SENTENCE_END.finditer(combined)]
            if len(ends) >= self.max_sentences:
                cut = ends[self.max_sentences - 1]
            elif len(combined) > self.max_chars:
                space = combined.rfind(" ", 0, self.max_chars)
                cut = space if space > start else self.max_chars

        if cut is None:
            self.text = combined
            return chunk

        self.done = True
        self.trimmed = bool(combined[cut:].strip())
        self.text = combined[:cut]
        return combined[start:cut]
