"""Tests for core.history."""
import time

import core.history as history


# ─── Fixture helper ──────────────────────────────────────────
def _isolate(monkeypatch, tmp_path):
    """Redirect the history file into a tmp directory."""
    fake = tmp_path / "history.json"
    monkeypatch.setattr(history, "HISTORY_FILE", fake)
    return fake


# ═══════════════════════════════════════════════════════════════
#  Empty / missing file
# ═══════════════════════════════════════════════════════════════
class TestEmptyState:
    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        assert history.list_entries() == []
        assert history.count() == 0

    def test_corrupt_file_returns_empty(self, monkeypatch, tmp_path):
        fake = _isolate(monkeypatch, tmp_path)
        fake.write_text("{ not valid json")
        assert history.list_entries() == []
        assert history.count() == 0

    def test_wrong_root_type_returns_empty(self, monkeypatch, tmp_path):
        fake = _isolate(monkeypatch, tmp_path)
        fake.write_text('"just a string"')
        assert history.list_entries() == []

    def test_entries_not_a_list(self, monkeypatch, tmp_path):
        fake = _isolate(monkeypatch, tmp_path)
        fake.write_text('{"version": 1, "entries": "oops"}')
        assert history.list_entries() == []


# ═══════════════════════════════════════════════════════════════
#  add()
# ═══════════════════════════════════════════════════════════════
class TestAdd:
    def test_creates_file(self, monkeypatch, tmp_path):
        fake = _isolate(monkeypatch, tmp_path)
        history.add("/src.mp4", "/out.txt", 10.0, "Russian",
                    "medium", "ok")
        assert fake.exists()

    def test_returns_entry_with_id(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/src.mp4", "/out.txt", 10.0, "Russian",
                        "medium", "ok")
        assert e["id"]
        assert e["source"] == "/src.mp4"
        assert e["output"] == "/out.txt"
        assert e["status"] == "ok"
        assert e["error"] is None
        assert e["duration"] == 10.0
        assert e["language"] == "Russian"
        assert e["model"] == "medium"

    def test_newest_first(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        history.add("/a.mp4", "/a.txt", 1.0, "en", "small", "ok")
        time.sleep(0.01)
        history.add("/b.mp4", "/b.txt", 2.0, "en", "small", "ok")
        entries = history.list_entries()
        assert entries[0]["source"] == "/b.mp4"
        assert entries[1]["source"] == "/a.mp4"

    def test_error_entry(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/broken.mp4", None, None, None, None,
                        "error", error="ffmpeg failed")
        assert e["status"] == "error"
        assert e["error"] == "E021"
        assert e["error_message"] == "ffmpeg failed"
        assert e["output"] == ""
        assert e["duration"] is None

    def test_unknown_status_becomes_error(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/x.mp4", "/x.txt", 1.0, "en", "small", "weird")
        assert e["status"] == "error"

    def test_none_paths_become_empty_strings(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add(None, None, None, None, None, "ok")
        assert e["source"] == ""
        assert e["output"] == ""


# ═══════════════════════════════════════════════════════════════
#  Cap at MAX_ENTRIES
# ═══════════════════════════════════════════════════════════════
class TestCap:
    def test_cap_keeps_newest(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        monkeypatch.setattr(history, "MAX_ENTRIES", 3)
        for i in range(5):
            history.add(f"/f{i}.mp4", f"/f{i}.txt", float(i),
                        "en", "small", "ok")
        entries = history.list_entries()
        assert len(entries) == 3
        # Newest three (indices 4, 3, 2).
        assert entries[0]["source"] == "/f4.mp4"
        assert entries[1]["source"] == "/f3.mp4"
        assert entries[2]["source"] == "/f2.mp4"


# ═══════════════════════════════════════════════════════════════
#  delete()
# ═══════════════════════════════════════════════════════════════
class TestDelete:
    def test_delete_existing(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e1 = history.add("/a.mp4", "/a.txt", 1.0, "en", "small", "ok")
        e2 = history.add("/b.mp4", "/b.txt", 1.0, "en", "small", "ok")
        assert history.delete(e1["id"]) is True
        entries = history.list_entries()
        assert len(entries) == 1
        assert entries[0]["id"] == e2["id"]

    def test_delete_missing_returns_false(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        assert history.delete("nonexistent-id") is False


# ═══════════════════════════════════════════════════════════════
#  clear()
# ═══════════════════════════════════════════════════════════════
class TestClear:
    def test_clear_removes_all(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        history.add("/a.mp4", "/a.txt", 1.0, "en", "small", "ok")
        history.add("/b.mp4", "/b.txt", 1.0, "en", "small", "ok")
        removed = history.clear()
        assert removed == 2
        assert history.list_entries() == []
        assert history.count() == 0

    def test_clear_on_empty_returns_zero(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        assert history.clear() == 0


# ═══════════════════════════════════════════════════════════════
#  Robustness
# ═══════════════════════════════════════════════════════════════
class TestRobustness:
    def test_entry_without_finished_at_sorted_last(self, monkeypatch, tmp_path):
        """An entry with a broken finished_at must not crash sorting."""
        fake = _isolate(monkeypatch, tmp_path)
        fake.write_text(
            '{"version": 1, "entries": ['
            '{"id":"a","finished_at":"oops"},'
            '{"id":"b","finished_at":9999999999}'
            ']}'
        )
        entries = history.list_entries()
        assert len(entries) == 2
        assert entries[0]["id"] == "b"

    def test_non_dict_entry_does_not_crash_list(self, monkeypatch, tmp_path):
        fake = _isolate(monkeypatch, tmp_path)
        fake.write_text('{"version": 1, "entries": ["oops", 42, null]}')
        # _read_raw passes the list through, list_entries sorts by
        # finished_at which is missing → default 0.
        # The critical guarantee is that it does not raise.
        entries = history.list_entries()
        assert isinstance(entries, list)

# ═══════════════════════════════════════════════════════════════
#  Error classification on add()
# ═══════════════════════════════════════════════════════════════
class TestErrorClassification:
    def test_raw_message_is_classified(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/x.mp4", None, None, None, None,
                        "error", error="ffmpeg failed to decode")
        assert e["error"] == "E021"
        assert e["error_message"] == "ffmpeg failed to decode"

    def test_existing_code_is_kept(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/x.mp4", None, None, None, None,
                        "error", error="E020")
        assert e["error"] == "E020"
        assert e["error_message"] is None

    def test_ok_status_has_no_error(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/x.mp4", "/x.txt", 1.0, "en", "small", "ok")
        assert e["error"] is None
        assert e["error_message"] is None

    def test_unknown_message_becomes_E099(self, monkeypatch, tmp_path):
        _isolate(monkeypatch, tmp_path)
        e = history.add("/x.mp4", None, None, None, None,
                        "error", error="something weird")
        assert e["error"] == "E099"
