"""Работа с моделями Whisper: поиск и автоматический выбор."""
import logging
from config import MODELS_DIR
from core.utils import get_duration

logger = logging.getLogger(__name__)


def find_models():
    """Список доступных ggml-моделей (без silero)."""
    if not MODELS_DIR.exists():
        return []
    return sorted(p.name for p in MODELS_DIR.glob("ggml-*.bin")
                  if "silero" not in p.name.lower())


def pick_auto_model(duration):
    """
    Автовыбор модели по длительности:
      < 5 мин   → small / medium / large-v3-turbo
      < 30 мин  → medium / large-v3-turbo
      иначе     → large-v3-turbo / large-v3 / medium
    """
    available = set(find_models())

    if duration is None or duration < 300:
        for m in ("ggml-small.bin", "ggml-medium.bin",
                  "ggml-large-v3-turbo.bin"):
            if m in available:
                return m

    if duration is not None and duration < 1800:
        for m in ("ggml-medium.bin", "ggml-large-v3-turbo.bin"):
            if m in available:
                return m

    for m in ("ggml-large-v3-turbo.bin", "ggml-large-v3.bin",
              "ggml-medium.bin"):
        if m in available:
            return m

    return sorted(available)[0] if available else None


def resolve_model(choice, media_path):
    """Превращает 'Авто' в реальное имя модели."""
    if choice != "Авто":
        return choice
    duration = get_duration(media_path)
    model = pick_auto_model(duration)
    if not model:
        raise RuntimeError("Нет доступных моделей")
    return model