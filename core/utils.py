"""Мелкие утилиты: работа с файлами, AppleScript, определение зависимостей."""
import os
import sys
import base64
import hashlib
import logging
import subprocess
from pathlib import Path
from shutil import which

from config import (
    ICON_DATA, ICON_PNG,
    WHISPER_BIN, FFMPEG_BIN, FFPROBE_BIN,
    MODELS_DIR, SOUND_DONE, SOUND_ERROR,
    REALTIME_FACTOR,
)

logger = logging.getLogger(__name__)

DEVNULL = subprocess.DEVNULL

def get_duration(path):
    """Длительность медиафайла в секундах (или None)."""
    try:
        r = subprocess.run(
            [FFPROBE_BIN, "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception as e:
        logger.debug(f"get_duration failed: {e}")
        return None

def get_media_info(path):
    """
    Возвращает (duration, size_mb) или (None, None).
    duration в секундах, size_mb в мегабайтах.
    """
    duration = get_duration(path)
    try:
        size_mb = Path(path).stat().st_size / (1024 * 1024)
    except Exception:
        size_mb = None
    return duration, size_mb

def estimate_processing_time(duration):
    """
    Оценка времени обработки в секундах.
    По умолчанию считаем что на M-чипах whisper быстрее реального
    времени примерно в REALTIME_FACTOR раз.
    """
    if not duration:
        return None
    return duration / REALTIME_FACTOR

def file_hash(path):
    """MD5-хэш файла (для кэша)."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def atomic_write(path, text):
    """Пишет файл атомарно: сначала .tmp, потом os.replace."""
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

def _escape_applescript(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')

def notify(title, msg):
    """Системное уведомление macOS."""
    t = _escape_applescript(title)
    m = _escape_applescript(msg)
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{m}" with title "{t}"'],
            check=False, stdout=DEVNULL, stderr=DEVNULL, timeout=3)
    except Exception as e:
        logger.debug(f"notify failed: {e}")

def play_sound(sound_type="done"):
    """
    Проигрывает системный звук macOS.
    sound_type: "done" (по умолчанию) или "error".
    """
    path = SOUND_DONE if sound_type == "done" else SOUND_ERROR
    if not Path(path).exists():
        logger.debug(f"Sound file not found: {path}")
        return
    try:
        subprocess.Popen(
            ["afplay", path],
            stdout=DEVNULL, stderr=DEVNULL,
        )
    except Exception as e:
        logger.debug(f"play_sound failed: {e}")

def open_in_finder(path):
    subprocess.run(["open", "-R", str(path)], check=False)

def open_file(path):
    subprocess.run(["open", str(path)], check=False)

def open_folder(path):
    subprocess.run(["open", str(path)], check=False)

def check_deps():
    """Проверяет, что модели и утилиты на месте."""
    problems = []
    if not MODELS_DIR.exists():
        problems.append(f"Не найдено папки моделей: {MODELS_DIR}")
    else:
        models = [p for p in MODELS_DIR.glob("ggml-*.bin")
                  if "silero" not in p.name.lower()]
        if not models:
            problems.append(f"Нет моделей в {MODELS_DIR}")

    for name, b in (("whisper-cli", WHISPER_BIN),
                    ("ffmpeg", FFMPEG_BIN),
                    ("ffprobe", FFPROBE_BIN)):
        if not Path(b).exists() and which(name) is None:
            problems.append(f"Не найдена команда: {name}")
    return problems

def get_icon_base64():
    """Возвращает base64 PNG-иконки или None."""
    try:
        sys.path.insert(0, str(ICON_DATA.parent))
        import icon_data
        if hasattr(icon_data, "ICON_BASE64"):
            return icon_data.ICON_BASE64
    except Exception as e:
        logger.debug(f"icon_data import failed: {e}")

    if ICON_PNG.exists():
        try:
            return base64.b64encode(ICON_PNG.read_bytes()).decode()
        except Exception:
            return None
    return None

def fmt_time(sec):
    """Секунды → 'м:сс' или 'ч:мм:сс'."""
    sec = int(max(0, sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def fmt_size(mb):
    """Мегабайты → '500 МБ' или '1.5 ГБ'."""
    if mb is None:
        return "?"
    if mb < 1:
        return f"{mb * 1024:.0f} КБ"
    if mb < 1024:
        return f"{mb:.0f} МБ"
    return f"{mb / 1024:.1f} ГБ"