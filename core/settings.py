"""Settings load and save."""
import json
import os
import locale
import logging

from config import (
    SETTINGS_FILE, DEFAULT_SETTINGS, LANGUAGES,
    get_lang_name_by_code,
)

logger = logging.getLogger(__name__)


def _detect_system_lang():
    """Detect the system language. Returns English if unknown."""
    code = None

    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            code = (val.split(":")[0]
                       .split(".")[0]
                       .split("_")[0]
                       .split("-")[0]
                       .lower())
            if code:
                break

    if not code:
        try:
            loc = locale.getlocale()[0]
            if loc:
                code = loc.split("_")[0].split("-")[0].lower()
        except Exception as e:
            logger.debug(f"locale detection failed: {e}")

    name = get_lang_name_by_code(code) if code else None
    if name:
        logger.info(f"System language: {code} -> {name}")
        return name

    logger.info("System language not detected, using English")
    return "English"


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = {**DEFAULT_SETTINGS, **data}

            if merged.get("lang") not in LANGUAGES:
                merged["lang"] = "English"

            if "ui_lang" not in merged:
                merged["ui_lang"] = _detect_system_lang()

            # Drop any stale keys that are no longer part of the app.
            merged.pop("theme", None)

            logger.info(f"Settings loaded: {merged}")
            return merged
        except Exception as e:
            logger.warning(f"Could not read settings: {e}")

    defaults = dict(DEFAULT_SETTINGS)
    sys_lang = _detect_system_lang()
    defaults["lang"] = sys_lang
    defaults["ui_lang"] = sys_lang
    return defaults


def save_settings(data):
    try:
        clean = dict(data)
        clean.pop("theme", None)
        SETTINGS_FILE.write_text(
            json.dumps(clean, ensure_ascii=False, indent=2),
            encoding="utf-8")
        logger.debug(f"Settings saved: {clean}")
    except Exception as e:
        logger.warning(f"Could not save settings: {e}")