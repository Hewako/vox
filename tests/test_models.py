"""Тесты для core.models."""
from unittest.mock import patch
from core.models import pick_auto_model


@patch("core.models.find_models")
def test_short_audio_picks_small(mock_find):
    mock_find.return_value = ["ggml-small.bin", "ggml-medium.bin",
                              "ggml-large-v3-turbo.bin"]
    assert pick_auto_model(60) == "ggml-small.bin"


@patch("core.models.find_models")
def test_short_audio_fallback_to_medium(mock_find):
    mock_find.return_value = ["ggml-medium.bin", "ggml-large-v3-turbo.bin"]
    assert pick_auto_model(60) == "ggml-medium.bin"


@patch("core.models.find_models")
def test_medium_audio_picks_medium(mock_find):
    mock_find.return_value = ["ggml-small.bin", "ggml-medium.bin",
                              "ggml-large-v3-turbo.bin"]
    assert pick_auto_model(900) == "ggml-medium.bin"


@patch("core.models.find_models")
def test_long_audio_picks_large(mock_find):
    mock_find.return_value = ["ggml-small.bin", "ggml-medium.bin",
                              "ggml-large-v3-turbo.bin"]
    assert pick_auto_model(3600) == "ggml-large-v3-turbo.bin"


@patch("core.models.find_models")
def test_no_models_returns_none(mock_find):
    mock_find.return_value = []
    assert pick_auto_model(60) is None


@patch("core.models.find_models")
def test_unknown_duration_picks_small(mock_find):
    mock_find.return_value = ["ggml-small.bin"]
    assert pick_auto_model(None) == "ggml-small.bin"