#!/usr/bin/env python3
"""
Vox — точка входа.
"""
import sys
import logging
from pathlib import Path

# Добавляем папку проекта в sys.path, чтобы работали импорты
sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_FILE, __version__
from core.utils import get_duration
from core.models import pick_auto_model
from core.transcriber import transcribe_one


# ─── Логирование ─────────────────────────────────────────────
# Configure the ROOT logger so every module in the project
# (core.*, ui.*) ends up in the same file and on the same stream.
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"))
_root_logger.addHandler(_fh)

_sh = logging.StreamHandler()
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
_root_logger.addHandler(_sh)

logger = logging.getLogger("vox")

logger.info(f"Vox {__version__} запущен")
logger.info(f"Аргументы запуска: {sys.argv}")


def _collect_launch_files():
    """
    Возвращает список путей к файлам, переданных при запуске.
    Работает при:
      - `open -a Vox.app file.mp4`
      - перетаскивании файла на иконку Vox в Dock
      - прямом вызове `python3 main.py file.mp4`
    """
    files = []
    for arg in sys.argv[1:]:
        # Пропускаем флаги (начинаются с -)
        if arg.startswith("-"):
            continue
        p = Path(arg)
        if p.exists() and p.is_file():
            files.append(str(p))
    return files


def run_cli(media_path, lang="ru"):
    media = Path(media_path)
    model = pick_auto_model(get_duration(media))
    out = transcribe_one(media, model, lang, use_vad=True,
                         on_status=lambda m: logger.info(m),
                         on_progress=lambda p: None)
    print(f"Готово: {out}")


if __name__ == "__main__":
    launch_files = _collect_launch_files()

    # Режим CLI — если передан только один файл и есть флаг -c
    if "-c" in sys.argv and launch_files:
        lang = "ru"
        if "-l" in sys.argv:
            lang = sys.argv[sys.argv.index("-l") + 1]
        run_cli(launch_files[0], lang)
        sys.exit(0)

    # GUI — обычный запуск или запуск с файлами из Dock
    from ui.window import run_gui
    run_gui(initial_files=launch_files)