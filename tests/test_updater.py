"""Tests for core.updater."""

import time

from core import updater

# Helper
class _FakeResponse:
    """Minimal stand-in for the object returned by urlopen()."""

    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

#  parse_version
class TestParseVersion:
    def test_three_parts(self):
        assert updater.parse_version("1.0.0") == (1, 0, 0, 0)

    def test_four_parts(self):
        assert updater.parse_version("1.2.3.4") == (1, 2, 3, 4)

    def test_two_parts_padded(self):
        assert updater.parse_version("1.0") == (1, 0, 0, 0)

    def test_empty_returns_zeros(self):
        assert updater.parse_version("") == (0, 0, 0, 0)

    def test_none_returns_zeros(self):
        assert updater.parse_version(None) == (0, 0, 0, 0)

    def test_non_numeric_returns_zeros(self):
        assert updater.parse_version("abc") == (0, 0, 0, 0)

    def test_mixed_parts(self):
        assert updater.parse_version("1.abc.3") == (1, 0, 3, 0)

    def test_more_than_four_parts_truncated(self):
        assert updater.parse_version("1.2.3.4.5") == (1, 2, 3, 4)

    def test_whitespace_stripped(self):
        assert updater.parse_version("  1.0.0  ") == (1, 0, 0, 0)

#  is_newer
class TestIsNewer:
    def test_patch_bump(self):
        assert updater.is_newer("1.0.1", "1.0.0") is True

    def test_same_version(self):
        assert updater.is_newer("1.0.0", "1.0.0") is False

    def test_older_version(self):
        assert updater.is_newer("1.0.0", "1.0.1") is False

    def test_major_bump(self):
        assert updater.is_newer("2.0.0", "1.9.9") is True

    def test_numeric_not_string_compare(self):
        # String comparison would say "1.9.0" > "1.10.0", but numeric
        # comparison correctly says "1.10.0" is newer.
        assert updater.is_newer("1.10.0", "1.9.0") is True

#  should_check
class TestShouldCheck:
    def test_no_file_returns_true(self, monkeypatch, tmp_path):
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", tmp_path / "missing.txt")
        assert updater.should_check() is True

    def test_fresh_file_returns_false(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.write_text(str(time.time()))
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        assert updater.should_check() is False

    def test_old_file_returns_true(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        two_days_ago = time.time() - 2 * 24 * 3600
        marker.write_text(str(two_days_ago))
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        assert updater.should_check() is True

    def test_corrupt_file_returns_true(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.write_text("not a number")
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        assert updater.should_check() is True

#  mark_checked
class TestMarkChecked:
    def test_creates_file(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        updater.mark_checked()
        assert marker.exists()

    def test_writes_fresh_timestamp(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        before = time.time()
        updater.mark_checked()
        after = time.time()
        ts = float(marker.read_text().strip())
        assert before <= ts <= after

#  fetch_manifest
class TestFetchManifest:
    def test_success(self, monkeypatch):
        payload = b'{"version": "1.0.1", "notes": "test"}'
        monkeypatch.setattr(updater, "urlopen", lambda *a, **kw: _FakeResponse(payload))
        assert updater.fetch_manifest() == {"version": "1.0.1", "notes": "test"}

    def test_invalid_json(self, monkeypatch):
        monkeypatch.setattr(
            updater, "urlopen", lambda *a, **kw: _FakeResponse(b"not json at all")
        )
        assert updater.fetch_manifest() is None

    def test_network_error(self, monkeypatch):
        def boom(*a, **kw):
            raise OSError("network down")

        monkeypatch.setattr(updater, "urlopen", boom)
        assert updater.fetch_manifest() is None

#  check_for_update (manual button)
class TestCheckForUpdate:
    def test_newer_returns_manifest(self, monkeypatch):
        monkeypatch.setattr(updater, "fetch_manifest", lambda: {"version": "99.0.0"})
        assert updater.check_for_update() == {"version": "99.0.0"}

    def test_same_returns_none(self, monkeypatch):
        from config import __version__

        monkeypatch.setattr(updater, "fetch_manifest", lambda: {"version": __version__})
        assert updater.check_for_update() is None

    def test_older_returns_none(self, monkeypatch):
        monkeypatch.setattr(updater, "fetch_manifest", lambda: {"version": "0.0.1"})
        assert updater.check_for_update() is None

    def test_missing_version_field(self, monkeypatch):
        monkeypatch.setattr(updater, "fetch_manifest", lambda: {"notes": "no version"})
        assert updater.check_for_update() is None

    def test_fetch_fails_returns_none(self, monkeypatch):
        monkeypatch.setattr(updater, "fetch_manifest", lambda: None)
        assert updater.check_for_update() is None

#  check_for_update_if_due (startup auto check)
class TestCheckForUpdateIfDue:
    def test_skips_when_not_due(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        marker.write_text(str(time.time()))  # fresh
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)

        called = []
        monkeypatch.setattr(updater, "fetch_manifest", lambda: called.append(1))

        result = updater.check_for_update_if_due()
        assert result is None
        assert called == []  # network was never touched

    def test_fetch_failure_does_not_write_marker(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"  # does not exist yet
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        monkeypatch.setattr(updater, "fetch_manifest", lambda: None)

        result = updater.check_for_update_if_due()
        assert result is None
        assert not marker.exists()  # marker must not be created

    def test_same_version_writes_marker(self, monkeypatch, tmp_path):
        from config import __version__

        marker = tmp_path / "marker.txt"
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        monkeypatch.setattr(updater, "fetch_manifest", lambda: {"version": __version__})

        result = updater.check_for_update_if_due()
        assert result is None
        assert marker.exists()

    def test_newer_version_returns_and_writes_marker(self, monkeypatch, tmp_path):
        marker = tmp_path / "marker.txt"
        monkeypatch.setattr(updater, "LAST_CHECK_FILE", marker)
        manifest = {"version": "99.0.0", "notes": "future release"}
        monkeypatch.setattr(updater, "fetch_manifest", lambda: manifest)

        result = updater.check_for_update_if_due()
        assert result == manifest
        assert marker.exists()
