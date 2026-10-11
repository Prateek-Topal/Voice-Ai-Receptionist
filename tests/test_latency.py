from receptionist.latency import LatencyTracker


def test_full_turn_uses_e2e_latency():
    t = LatencyTracker()
    t.on_user_message({"end_of_turn_delay": 0.5})
    turn = t.on_assistant_message({"llm_node_ttft": 0.3, "tts_node_ttfb": 0.2, "e2e_latency": 0.8})
    assert turn is not None
    assert turn.e2e == 0.8
    assert turn.end_of_turn == 0.5
    assert t.summary()["turns"] == 1


def test_falls_back_to_sum_without_e2e():
    t = LatencyTracker()
    t.on_user_message({"end_of_turn_delay": 0.5})
    turn = t.on_assistant_message({"llm_node_ttft": 0.3, "tts_node_ttfb": 0.2})
    assert round(turn.e2e, 2) == 1.0


def test_greeting_without_llm_is_ignored():
    t = LatencyTracker()
    assert t.on_assistant_message({"tts_node_ttfb": 0.2}) is None
    assert t.summary() == {"turns": 0}


def test_summary():
    t = LatencyTracker()
    for e2e in (0.8, 1.2, 2.0):
        t.on_user_message({"end_of_turn_delay": 0.4})
        t.on_assistant_message({"llm_node_ttft": 0.3, "tts_node_ttfb": 0.2, "e2e_latency": e2e})
    s = t.summary()
    assert s["turns"] == 3
    assert s["median_total_s"] == 1.2
    assert s["max_total_s"] == 2.0
    assert s["under_1s_pct"] == 33
    assert s["avg_endpointing_s"] == 0.4
