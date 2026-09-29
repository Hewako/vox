"""
Проверка и установка обновлений Vox.

Как это работает:

1. Раз в сутки (или по кнопке в About) приложение тянет version.json
   из репозитория — там указана актуальная версия и ссылка на .zip.
2. Если версия новее текущей, пользователь видит баннер.
3. По нажатию скачивается .zip, распаковывается в /tmp.
4. Запускается вспомогательный bash-скрипт, который ждёт выхода
   Vox, подменяет /Applications/Vox.app и запускает его заново.
"""
import os
import sys
import json
import time
import shutil
import zipfile
import logging
import tempfile
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request

from config import (
    __version__, UPDATE_URL, UPDATE_CHECK_INTERVAL_HOURS,
    APP_SUPPORT,
)

logger = logging.getLogger(__name__)

LAST_CHECK_FILE = APP_SUPPORT / "last_update_check.txt"


# ─── Версии ──────────────────────────────────────────────────
def parse_version(v):
    """'1.0.0' -> (1, 0, 0, 0). Ошибки превращаются в нули."""
    if not v:
        return (0, 0, 0, 0)
    parts = str(v).strip().split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def is_newer(remote, current):
    """True, если remote > current."""
    return parse_version(remote) > parse_version(current)


# ─── Проверка ────────────────────────────────────────────────
def fetch_manifest():
    """Скачивает version.json. Возвращает dict или None."""
    try:
        req = Request(UPDATE_URL, headers={
            "User-Agent": f"Vox/{__version__}",
            "Cache-Control": "no-cache",
        })
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except Exception as e:
        logger.info(f"update: fetch failed: {e}")
        return None


def check_for_update():
    """
    Возвращает dict {'version', 'download_url', 'notes'}
    если есть версия новее текущей, иначе None.
    """
    data = fetch_manifest()
    if not data:
        return None

    remote_v = data.get("version")
    if not remote_v:
        logger.info("update: version.json без поля version")
        return None

    if not is_newer(remote_v, __version__):
        logger.info(f"update: {remote_v} не новее {__version__}")
        return None

    logger.info(f"update: доступна версия {remote_v}")
    return data


def should_check():
    """Прошло ли с последней проверки больше N часов."""
    try:
        if not LAST_CHECK_FILE.exists():
            return True
        last = float(LAST_CHECK_FILE.read_text().strip())
        elapsed_h = (time.time() - last) / 3600
        return elapsed_h >= UPDATE_CHECK_INTERVAL_HOURS
    except Exception:
        return True


def mark_checked():
    """Запоминает время последней проверки."""
    try:
        LAST_CHECK_FILE.write_text(str(time.time()))
    except Exception as e:
        logger.debug(f"update: mark_checked failed: {e}")


def check_for_update_if_due():
    """
    Проверяет обновление, если с прошлого раза прошло достаточно времени.
    Безопасно вызывать из фонового потока.
    """
    if not should_check():
        return None
    mark_checked()
    return check_for_update()


# ─── Скачивание ──────────────────────────────────────────────
def download_file(url, dest, on_progress=None):
    """Скачивает url в dest. on_progress(done, total) вызывается по мере загрузки."""
    on_progress = on_progress or (lambda d, t: None)
    req = Request(url, headers={"User-Agent": f"Vox/{__version__}"})

    with urlopen(req, timeout=30) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        chunk_size = 256 * 1024

        with open(dest, "wb") as f:
            while True:
                buf = resp.read(chunk_size)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                on_progress(done, total)

    return dest


# ─── Установка ───────────────────────────────────────────────
def _find_app_bundle():
    """
    Возвращает путь к текущему .app или None,
    если приложение запущено из исходников (python main.py).
    """
    for candidate in (sys.executable,
                      sys.argv[0] if sys.argv else ""):
        if ".app/Contents/MacOS/" in candidate:
            app_path = candidate.split(".app/Contents/MacOS/")[0] + ".app"
            return Path(app_path)
    return None


def install_update(zip_path, on_status=None):
    """
    Распаковывает скачанный zip и подменяет текущий Vox.app.
    Возвращает True, если удалось запустить установку.
    Само приложение после этого должно сразу закрыться —
    замена произойдёт уже без него.
    """
    on_status = on_status or (lambda m: None)
    zip_path = Path(zip_path)

    if not zip_path.exists():
        raise FileNotFoundError(f"Файл не найден: {zip_path}")

    current_app = _find_app_bundle()
    if current_app is None:
        raise RuntimeError(
            "Vox запущен не из .app. Автообновление доступно "
            "только для собранного приложения."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="vox_update_"))
    on_status("Распаковка…")

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_dir)

    new_app = None
    for candidate in tmp_dir.rglob("Vox.app"):
        new_app = candidate
        break

    if new_app is None or not new_app.exists():
        raise RuntimeError("Vox.app не найден внутри архива")

    # Сначала переносим распакованное приложение наружу tmp_dir,
    # чтобы rm -rf в конце не задел его.
    staging = Path(tempfile.mkdtemp(prefix="vox_staging_"))
    staged_app = staging / "Vox.app"
    shutil.move(str(new_app), str(staged_app))

    # Helper-скрипт живёт вне временных папок, чтобы точно дожил.
    helper = Path(tempfile.gettempdir()) / "vox_update_helper.sh"
    helper.write_text(f"""#!/bin/bash
# Ждём, пока Vox завершится
sleep 1

# Подменяем приложение
rm -rf "{current_app}"
mv "{staged_app}" "{current_app}"
xattr -cr "{current_app}" 2>/dev/null

# Запускаем обновлённый Vox
open "{current_app}"

# Подчищаем мусор
rm -rf "{staging}"
rm -rf "{tmp_dir}"
rm -f "{helper}"
""")
    os.chmod(helper, 0o755)

    on_status("Перезапуск…")

    subprocess.Popen(
        ["/bin/bash", str(helper)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return True