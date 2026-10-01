"""Tests for core.settings."""

import json

import core.settings as settings_mod

def _stub_system_lang(monkeypatch, value="English"):
    """Make system-language detection deterministic for tests."""
    monkeypatch.setattr(settings_mod, "_detect_system_lang", lambda: value)

def test_load_settings_returns_defaults_when_no_file(tmp_path, monkeypatch):
    fake_file = tmp_path / "nonexistent.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    _stub_system_lang(monkeypatch, "English")

    s = settings_mod.load_settings()
    assert s["lang"] == "English"
    assert s["ui_lang"] == "English"
    assert s["vad"] is True

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    _stub_system_lang(monkeypatch, "English")

    data = {
        "lang": "German",
        "model": "Авто",
        "vad": False,
        "cache": True,
        "srt": True,
        "workers": "2",
    }
    settings_mod.save_settings(data)
    loaded = settings_mod.load_settings()
    assert loaded["lang"] == "German"
    assert loaded["vad"] is False
    assert loaded["srt"] is True

def test_load_settings_handles_broken_json(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    fake_file.write_text("{ broken json")
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    _stub_system_lang(monkeypatch, "English")

    s = settings_mod.load_settings()
    # Falls back to defaults when the file is unreadable.
    assert s["lang"] == "English"

def test_load_settings_merges_with_defaults(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    fake_file.write_text(json.dumps({"lang": "English"}))
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    _stub_system_lang(monkeypatch, "English")

    s = settings_mod.load_settings()
    assert s["lang"] == "English"
    assert s["vad"] is True  # from defaults

def test_load_settings_rejects_unknown_language(tmp_path, monkeypatch):
    """A lang value outside config.LANGUAGES falls back to English."""
    fake_file = tmp_path / "settings.json"
    fake_file.write_text(json.dumps({"lang": "Klingon"}))
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)

    s = settings_mod.load_settings()
    assert s["lang"] == "English"
