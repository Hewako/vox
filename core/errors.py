"""
Error codes for Vox.

Every failure that reaches the history gets a short code like E020.
The code is stable and language-independent; the human-readable
description is looked up separately (and can later be fetched from
the repo, like version.json).

Codes are grouped by area:

    E0xx  Files and input
    E01x  External dependencies (whisper-cli, ffmpeg, models)
    E02x  Transcription process
    E03x  Resources (memory, disk, cpu)
    E099  Unknown

The classifier inspects the exception type and message and returns
the most specific matching code, falling back to E099.
"""
import logging

logger = logging.getLogger(__name__)


# ─── Catalogue ───────────────────────────────────────────────
# Short English fallback descriptions. Full localized text will be
# fetched from the repo in a later iteration.
CODES = {
    "E001": "Source file not found",
    "E002": "Could not read media information",
    "E003": "Unsupported media format",
    "E004": "Output folder is not writable",
    "E010": "whisper-cli not found",
    "E011": "ffmpeg not found",
    "E012": "ffprobe not found",
    "E013": "Whisper model not found",
    "E020": "Whisper failed",
    "E021": "FFmpeg failed",
    "E022": "Process timed out",
    "E023": "Cancelled by user",
    "E030": "Out of memory",
    "E031": "Out of disk space",
    "E032": "System resources exhausted",
    "E099": "Unknown error",
}


def describe(code: str) -> str:
    """Return a short English description for a code."""
    return CODES.get(code, CODES["E099"])


# ─── Classifier ──────────────────────────────────────────────
def classify(exc) -> str:
    """
    Map an exception (or a raw error string) to an error code.

    The function is intentionally tolerant: it looks at the exception
    type first, then scans the message for keywords. It always
    returns a valid code, never None.
    """
    # Exception type checks (most reliable).
    if isinstance(exc, FileNotFoundError):
        msg = str(exc).lower()
        if "whisper" in msg:
            return "E010"
        if "ffmpeg" in msg:
            return "E011"
        if "ffprobe" in msg:
            return "E012"
        return "E001"
    if isinstance(exc, PermissionError):
        return "E004"
    if isinstance(exc, MemoryError):
        return "E030"
    if isinstance(exc, TimeoutError):
        return "E022"

    # Fall back to keyword scanning.
    msg = str(exc).lower() if exc else ""

    if not msg:
        return "E099"

    # Explicit user cancellation often comes through as a message.
    if "cancel" in msg or "отмен" in msg:
        return "E023"

    # Dependencies.
    if "whisper-cli" in msg and ("not found" in msg or "no such file" in msg):
        return "E010"
    if "ffmpeg" in msg and ("not found" in msg or "no such file" in msg):
        return "E011"
    if "ffprobe" in msg and ("not found" in msg or "no such file" in msg):
        return "E012"
    if "model" in msg and ("not found" in msg or "no such file" in msg):
        return "E013"

    # Process failures.
    if "whisper" in msg and ("fail" in msg or "error" in msg):
        return "E020"
    if "ffmpeg" in msg and ("fail" in msg or "error" in msg):
        return "E021"
    if "timeout" in msg or "timed out" in msg:
        return "E022"

    # Resources.
    if "out of memory" in msg or "memoryerror" in msg:
        return "E030"
    if "no space" in msg or "disk full" in msg:
        return "E031"
    if "resource" in msg and "exhaust" in msg:
        return "E032"

    # Media input.
    if "unsupported" in msg or "format not supported" in msg:
        return "E003"
    if "could not read" in msg or "ffprobe" in msg:
        return "E002"

    return "E099"


# ─── Localized description ───────────────────────────────────
def describe_localized(code: str) -> str:
    """
    Return a localized human-readable description for a code.

    Looks up the key `error_<CODE>` in i18n. If the translation is
    missing, falls back to the short English description from CODES.
    Unknown codes are treated as E099.
    """
    from i18n import t

    if code not in CODES:
        code = "E099"

    key = f"error_{code}"
    val = t(key)
    if val == key:
        # No translation found — t() returned the key unchanged.
        return CODES[code]
    return val
