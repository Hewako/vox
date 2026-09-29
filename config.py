"""
Vox — конфигурация: версия, пути, палитра, константы.
"""
import os
from pathlib import Path
from shutil import which

__version__ = "1.0.0"

# ─── PATH fix для .app ───────────────────────────────────────
_EXTRA = ["/opt/homebrew/bin", "/usr/local/bin"]
_cur = os.environ.get("PATH", "")
for _p in _EXTRA:
    if _p not in _cur.split(":"):
        _cur = _p + ":" + _cur
os.environ["PATH"] = _cur


# ─── Пути ────────────────────────────────────────────────────
HOME = Path.home()
MODELS_DIR = HOME / "whisper-models"
CACHE_DIR = HOME / ".whisper_cache"
LOG_DIR = HOME / "Library" / "Logs"
LOG_FILE = LOG_DIR / "Vox.log"
APP_SUPPORT = HOME / "Library" / "Application Support" / "Vox"
SETTINGS_FILE = APP_SUPPORT / "settings.json"
HISTORY_FILE = APP_SUPPORT / "history.json"

_THIS_DIR = Path(__file__).parent
ICON_DATA = _THIS_DIR / "icon_data.py"
ICON_PNG = HOME / "Desktop" / "icon.png"

VAD_MODEL_NAME = "ggml-silero-v5.1.2.bin"
VAD_MODEL = MODELS_DIR / VAD_MODEL_NAME

MAX_CACHE_MB = 500

CACHE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
APP_SUPPORT.mkdir(parents=True, exist_ok=True)


# ─── Бинарники ───────────────────────────────────────────────
def _find_bin(name):
    p = which(name)
    if p:
        return p
    for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        candidate = Path(d) / name
        if candidate.exists():
            return str(candidate)
    return name


WHISPER_BIN = _find_bin("whisper-cli")
FFMPEG_BIN = _find_bin("ffmpeg")
FFPROBE_BIN = _find_bin("ffprobe")


# ─── Языки для расшифровки ───────────────────────────────────
TOP_LANGUAGES = [
    ("English", "en"),
    ("Spanish", "es"),
    ("Russian", "ru"),
    ("Chinese", "zh"),
    ("Hindi", "hi"),
    ("Arabic", "ar"),
    ("Portuguese", "pt"),
]


WORLD_LANGUAGES = [
    ("English", "en"),
    ("Chinese", "zh"),
    ("Hindi", "hi"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("Arabic", "ar"),
    ("Bengali", "bn"),
    ("Portuguese", "pt"),
    ("Russian", "ru"),
    ("Urdu", "ur"),
    ("Indonesian", "id"),
    ("German", "de"),
    ("Japanese", "ja"),
    ("Punjabi", "pa"),
    ("Marathi", "mr"),
]


ALL_LANGUAGES = [
    ("Afrikaans", "af"),
    ("Albanian", "sq"),
    ("Amharic", "am"),
    ("Arabic", "ar"),
    ("Armenian", "hy"),
    ("Assamese", "as"),
    ("Azerbaijani", "az"),
    ("Bashkir", "ba"),
    ("Basque", "eu"),
    ("Belarusian", "be"),
    ("Bengali", "bn"),
    ("Bosnian", "bs"),
    ("Breton", "br"),
    ("Bulgarian", "bg"),
    ("Burmese", "my"),
    ("Cantonese", "yue"),
    ("Catalan", "ca"),
    ("Chinese", "zh"),
    ("Croatian", "hr"),
    ("Czech", "cs"),
    ("Danish", "da"),
    ("Dutch", "nl"),
    ("English", "en"),
    ("Estonian", "et"),
    ("Faroese", "fo"),
    ("Finnish", "fi"),
    ("French", "fr"),
    ("Galician", "gl"),
    ("Georgian", "ka"),
    ("German", "de"),
    ("Greek", "el"),
    ("Gujarati", "gu"),
    ("Haitian Creole", "ht"),
    ("Hausa", "ha"),
    ("Hawaiian", "haw"),
    ("Hebrew", "he"),
    ("Hindi", "hi"),
    ("Hungarian", "hu"),
    ("Icelandic", "is"),
    ("Indonesian", "id"),
    ("Italian", "it"),
    ("Japanese", "ja"),
    ("Javanese", "jw"),
    ("Kannada", "kn"),
    ("Kazakh", "kk"),
    ("Khmer", "km"),
    ("Korean", "ko"),
    ("Lao", "lo"),
    ("Latin", "la"),
    ("Latvian", "lv"),
    ("Lingala", "ln"),
    ("Lithuanian", "lt"),
    ("Luxembourgish", "lb"),
    ("Macedonian", "mk"),
    ("Malagasy", "mg"),
    ("Malay", "ms"),
    ("Malayalam", "ml"),
    ("Maltese", "mt"),
    ("Maori", "mi"),
    ("Marathi", "mr"),
    ("Mongolian", "mn"),
    ("Nepali", "ne"),
    ("Norwegian", "no"),
    ("Nynorsk", "nn"),
    ("Occitan", "oc"),
    ("Pashto", "ps"),
    ("Persian", "fa"),
    ("Polish", "pl"),
    ("Portuguese", "pt"),
    ("Punjabi", "pa"),
    ("Romanian", "ro"),
    ("Russian", "ru"),
    ("Sanskrit", "sa"),
    ("Serbian", "sr"),
    ("Shona", "sn"),
    ("Sindhi", "sd"),
    ("Sinhala", "si"),
    ("Slovak", "sk"),
    ("Slovenian", "sl"),
    ("Somali", "so"),
    ("Spanish", "es"),
    ("Sundanese", "su"),
    ("Swahili", "sw"),
    ("Swedish", "sv"),
    ("Tagalog", "tl"),
    ("Tajik", "tg"),
    ("Tamil", "ta"),
    ("Tatar", "tt"),
    ("Telugu", "te"),
    ("Thai", "th"),
    ("Tibetan", "bo"),
    ("Turkish", "tr"),
    ("Turkmen", "tk"),
    ("Ukrainian", "uk"),
    ("Urdu", "ur"),
    ("Uzbek", "uz"),
    ("Vietnamese", "vi"),
    ("Welsh", "cy"),
    ("Yiddish", "yi"),
    ("Yoruba", "yo"),
]


LANGUAGES = {"Авто": "auto"}
for name, code in ALL_LANGUAGES:
    LANGUAGES[name] = code


LANG_CODE_TO_NAME = {code: name for name, code in ALL_LANGUAGES}


# ─── Языки интерфейса (i18n) ─────────────────────────────────
UI_LANGUAGES = {
    "en": "English",
    "ru": "Русский",
    "es": "Español",
    "zh": "中文",
    "hi": "हिन्दी",
    "ar": "العربية",
    "pt": "Português",
    "de": "Deutsch",
    "ja": "日本語",
    "fr": "Français",
    "pl": "Polski",
    "sr": "Srpski",
}

UI_LANG_NAME_TO_CODE = {v: k for k, v in UI_LANGUAGES.items()}


# ─── Размеры шрифта ──────────────────────────────────────────
FONT_SIZES = {
    "small":  {"ui": 10, "title": 18, "small": 9,  "mono": 9,  "btn": 10},
    "medium": {"ui": 12, "title": 22, "small": 10, "mono": 10, "btn": 11},
    "large":  {"ui": 14, "title": 26, "small": 12, "mono": 12, "btn": 13},
}

FONT_SIZE_ORDER = ["small", "medium", "large"]


# ─── Валидация файлов ────────────────────────────────────────
WARN_DURATION_MIN = 60
WARN_ESTIMATED_TIME_MIN = 30
REALTIME_FACTOR = 10


# ─── Звуки завершения ────────────────────────────────────────
SOUND_DONE = "/System/Library/Sounds/Glass.aiff"
SOUND_ERROR = "/System/Library/Sounds/Basso.aiff"


# ─── Функции для языка расшифровки ───────────────────────────
def get_combo_values():
    """Значения для Combobox языков расшифровки (с разделителями)."""
    from i18n import t
    values = [t("lang_auto"), t("sep_popular")]
    values.extend([name for name, _ in TOP_LANGUAGES])
    values.append(t("sep_all"))
    values.extend([name for name, _ in ALL_LANGUAGES])
    return values


def is_separator(value):
    """True, если значение — разделитель."""
    from i18n import t
    return value in (t("sep_popular"), t("sep_all"))


def get_lang_name_by_code(code):
    """Название языка по коду ISO 639-1. None если не найдено."""
    if not code:
        return None
    return LANG_CODE_TO_NAME.get(code.lower())


def get_world_lang_names():
    """Названия топ-15 языков (100+ млн говорящих)."""
    return [name for name, _ in WORLD_LANGUAGES]


# ─── Функции для модели ──────────────────────────────────────
def get_model_choices():
    """Значения для Combobox моделей. Локализованный «Авто» впереди."""
    from i18n import t
    from core.models import find_models
    return [t("model_auto")] + find_models()


def model_to_internal(value):
    """Локализованное значение → внутреннее."""
    from i18n import t
    if value == t("model_auto"):
        return "Авто"
    return value


def model_to_display(internal_value):
    """Внутреннее значение → локализованное."""
    from i18n import t
    if internal_value == "Авто":
        return t("model_auto")
    return internal_value


# ─── Дефолтные настройки ─────────────────────────────────────
DEFAULT_SETTINGS = {
    "lang": "English",
    "ui_lang": "en",
    "model": "Авто",
    "vad": True,
    "cache": True,
    "srt": False,
    "workers": "1",
    "font_size": "medium",
    "sound_on_done": True,
    "warn_long_files": True,
}


# ─── Палитра (тёмная тема) ───────────────────────────────────
BG           = "#1e1e1e"
BG_CARD      = "#252528"
BG_INPUT     = "#2c2c2e"
FG           = "#e8e8e8"
FG_SUBTLE    = "#8e8e93"
FG_DIM       = "#6c6c70"
ACCENT       = "#0a84ff"
ACCENT_HOVER = "#3395ff"
BORDER       = "#3a3a3c"
SUCCESS      = "#30d158"
DANGER       = "#ff453a"
DANGER_HOVER = "#ff6961"


# ─── Функции для шрифта ──────────────────────────────────────
def get_font(size_key=None, kind="ui"):
    """Возвращает кортеж шрифта. kind: ui | title | small | mono | btn."""
    key = size_key or "medium"
    if key not in FONT_SIZES:
        key = "medium"
    size = FONT_SIZES[key].get(kind, 12)
    family = "Menlo" if kind == "mono" else "Helvetica"
    if kind in ("title", "btn"):
        return (family, size, "bold")
    return (family, size)