"""Day 7: caller ID, secret-mounted key file, time limit outcome."""

from receptionist import config
from receptionist.call_record import CallRecord
from receptionist.caller_id import caller_id_capability, caller_number


def test_caller_number_from_sip_attributes():
    assert caller_number({"sip.phoneNumber": "+919876543210"}) == "9876543210"
    assert caller_number({"sip.phoneNumber": "+14155550123"}) is None  # US number, 11 digits
    assert caller_number({}) is None
    assert caller_number(None) is None


def test_caller_id_capability_reads_only_last_four():
    text = caller_id_capability("9876543210")
    assert "ending in 3 2 1 0" in text and "9876543210" in text


# def test_secret_mount_fallback(tmp_path, monkeypatch):
#     mounted = tmp_path / "google-service-account.json"
#     mounted.write_text("{}")
#     monkeypatch.setattr(config, "SECRET_MOUNT_DIR", tmp_path)
#     resolved = config._path("credentials/google-service-account.json")
#     assert resolved == mounted  # local file missing -> uses the mounted secret

def test_secret_mount_fallback(tmp_path, monkeypatch):
    name = "test-only-missing-key.json"  # never exists locally
    mounted = tmp_path / name
    mounted.write_text("{}")
    monkeypatch.setattr(config, "SECRET_MOUNT_DIR", tmp_path)
    resolved = config._path(f"credentials/{name}")
    assert resolved == mounted  # local file missing -> uses the mounted secret


def test_local_file_wins_over_mounted_secret(tmp_path, monkeypatch):
    local = tmp_path / "local" / "key.json"
    local.parent.mkdir()
    local.write_text("{}")
    (tmp_path / "key.json").write_text("{}")
    monkeypatch.setattr(config, "SECRET_MOUNT_DIR", tmp_path)
    assert config._path(str(local)) == local  # your laptop: real file is used


def test_time_limit_is_a_failure_unless_task_done():
    r = CallRecord(room="t")
    r.say("CALLER", "hi")
    r.end("time_limit")
    assert r.outcome() == ("failed", "call hit the time limit")
    r2 = CallRecord(room="t")
    r2.tool("book_appointment", "BOOKED: x")
    r2.end("time_limit")
    assert r2.outcome()[0] == "booked"
