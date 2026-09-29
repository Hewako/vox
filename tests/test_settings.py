"""Тесты для core.settings."""
import json
import core.settings as settings_mod


def test_load_settings_returns_defaults_when_no_file(tmp_path, monkeypatch):
    fake_file = tmp_path / "nonexistent.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    s = settings_mod.load_settings()
    assert s["lang"] == "Русский"
    assert s["vad"] is True


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)

    data = {"lang": "Deutsch", "model": "Авто", "vad": False,
            "cache": True, "srt": True, "workers": "2"}
    settings_mod.save_settings(data)
    loaded = settings_mod.load_settings()
    assert loaded["lang"] == "Deutsch"
    assert loaded["vad"] is False
    assert loaded["srt"] is True


def test_load_settings_handles_broken_json(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    fake_file.write_text("{ broken json")
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    s = settings_mod.load_settings()
    assert s["lang"] == "Русский"  # откат к дефолтам


def test_load_settings_merges_with_defaults(tmp_path, monkeypatch):
    fake_file = tmp_path / "settings.json"
    fake_file.write_text(json.dumps({"lang": "English"}))
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", fake_file)
    s = settings_mod.load_settings()
    assert s["lang"] == "English"
    assert s["vad"] is True  # из дефолтов