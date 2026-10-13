from receptionist.reply_guard import ReplyLimiter


def run(chunks, **kw):
    lim = ReplyLimiter(**kw)
    out = ""
    for c in chunks:
        out += lim.feed(c)
        if lim.done:
            break
    return out, lim


def test_cuts_after_first_question_glued_to_next_turn():
    # Real output from a test call: the model kept talking for the caller.
    chunks = ["Thanks, Rakesh. What service would you like? Is it a tooth removal?", "Got it. When"]
    out, lim = run(chunks)
    assert out == "Thanks, Rakesh. What service would you like?"
    assert lim.trimmed


def test_question_mark_without_space():
    out, _ = run(["Great. May I have your full name, please?Sure thing. What's your"])
    assert out == "Great. May I have your full name, please?"


def test_question_split_across_chunks():
    out, _ = run(["Could you tell me", " your number", "?", " So your number is nine"])
    assert out == "Could you tell me your number?"


def test_normal_reply_untouched():
    text = "Perfect. Our team will call you back. Is there anything else I can help with?"
    out, lim = run([text[:20], text[20:]])
    assert out == text
    assert not lim.trimmed


def test_long_statement_capped_by_sentences():
    out, lim = run(["One. Two. Three. Four. Five. Six."])
    assert out == "One. Two. Three. Four."
    assert lim.trimmed


def test_very_long_sentence_capped_by_chars():
    out, _ = run(["word " * 100], max_chars=50)
    assert len(out) <= 50
