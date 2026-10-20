from receptionist.call_record import CallRecord, mask_numbers
from receptionist.metrics import call_stats, eval_stats, latency_stats, percentile, render_markdown


def test_mask_numbers():
    assert mask_numbers("my number is 98765 43210") == "my number is ******3210"
    assert mask_numbers("at 11:30 on 15 October") == "at 11:30 on 15 October"  # not a phone


def _call(*tools, end="caller_goodbye", errors=(), spoke=True):
    r = CallRecord(room="t")
    if spoke:
        r.say("CALLER", "hi")
    for name, result in tools:
        r.tool(name, result)
    for e in errors:
        r.error(e)
    r.end(end)
    return r


def test_outcomes():
    assert _call(("check_availability", "AVAILABLE: x"), ("book_appointment", "BOOKED: x")
                 ).outcome()[0] == "booked"
    assert _call(("find_booking", "FOUND: 1"), ("cancel_appointment", "CANCELLED: x")
                 ).outcome()[0] == "cancelled"
    assert _call().outcome()[0] == "info_only"
    assert _call(("check_availability", "AVAILABLE: x")).outcome()[0] == "incomplete"
    assert _call(end="silence_timeout").outcome()[0] == "failed"
    assert _call(("check_availability", "ERROR: calendar down")).outcome()[0] == "failed"
    assert _call(spoke=False, end="user_initiated").outcome() == ("failed", "caller never spoke")


def test_blocked_booking_then_booked_counts_as_booked():
    r = _call(("book_appointment", "NOT BOOKED: not confirmed"), ("book_appointment", "BOOKED: x"))
    assert r.outcome()[0] == "booked"


def test_first_end_reason_wins():
    r = CallRecord(room="t")
    r.end("caller_goodbye")
    r.end("user_initiated")
    assert r.end_reason == "caller_goodbye"


def test_record_masks_phone_in_transcript_and_tools():
    r = _call(("find_booking", "NOT FOUND: no appointments for 9876543210"))
    d = r.to_dict()
    assert "9876543210" not in str(d)


def test_percentile():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([], 50) is None


def _rec(outcome, success, e2es=(), reason="r"):
    return {
        "outcome": outcome, "success": success, "reason": reason, "duration_s": 60,
        "latency": {"interruptions": 1},
        "latency_turns": [{"e2e": e, "end_of_turn": 0.5, "llm_ttft": 0.4, "tts_ttfb": 0.2}
                          for e in e2es],
    }


def test_call_and_latency_stats():
    calls = [
        _rec("booked", True, [0.8, 1.2]),
        _rec("cancelled", True, [1.6]),
        _rec("incomplete", False, [2.5], reason="started a task"),
        _rec("info_only", True, [0.9]),
        _rec("failed", False, [], reason="caller went silent") | {"had_intent": False},
    ]
    cs = call_stats(calls)
    assert cs["calls"] == 5 and cs["successful_bookings"] == 1 and cs["cancellations"] == 1
    assert cs["task_completion_pct"] == 67  # 2 of 3 calls that wanted something done
    assert cs["failed_calls"] == 2  # the silent call is a failed conversation...
    assert cs["failure_reasons"] == {"started a task": 1, "caller went silent": 1}
    lat = latency_stats(calls)
    assert lat["turns"] == 5 and lat["p50_s"] == 1.2 and lat["under_1s_pct"] == 40


def test_eval_stats_across_runs():
    runs = [
        {"timestamp": "a", "model": "m", "passed": 1, "total": 2, "results": [
            {"name": "x", "category": "c", "passed": True},
            {"name": "y", "category": "c", "passed": False}]},
        {"timestamp": "b", "model": "m", "passed": 2, "total": 2, "results": [
            {"name": "x", "category": "c", "passed": True},
            {"name": "y", "category": "c", "passed": True}]},
    ]
    ev = eval_stats(runs)
    assert ev["pass_rate_pct"] == 75 and ev["scenarios"]["y"]["passed"] == 1
    assert ev["latest"]["timestamp"] == "b"


def test_report_renders_with_and_without_data():
    empty = render_markdown([], [], "now")
    assert "No calls recorded yet" in empty and "No eval runs yet" in empty
    full = render_markdown([_rec("booked", True, [0.8])], [], "now",
                           latency_only=[{"latency_turns": [{"e2e": 1.0}]}])
    assert "Successful bookings | 1" in full and "2 agent turns" in full
