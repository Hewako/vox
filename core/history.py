"""
History of transcriptions.

Stores every finished job (successful or failed) in a small JSON file
next to settings.json. Entries are kept newest-first, capped at
MAX_ENTRIES. Older records are dropped silently.

Public API:
    load()                   -- read all entries
    add(...)                 -- append one entry
    list_entries()           -- read entries, newest first
    delete(entry_id)         -- remove one entry by id
    clear()                  -- drop all entries
    count()                  -- number of entries

All file operations are safe against missing or corrupt JSON: they
fall back to an empty history rather than raising.
"""
import json
import logging
import time
import uuid

from config import HISTORY_FILE

logger = logging.getLogger(__name__)


# ─── Config ──────────────────────────────────────────────────
MAX_ENTRIES = 200
SCHEMA_VERSION = 1


# ─── Internal load/save ──────────────────────────────────────
def _read_raw() -> dict:
    """Read the history file. Returns {'version': ..., 'entries': [...]}."""
    if not HISTORY_FILE.exists():
        return {"version": SCHEMA_VERSION, "entries": []}

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("history root is not a dict")
        entries = data.get("entries", [])
        if not isinstance(entries, list):
            raise ValueError("entries is not a list")
        return {
            "version": data.get("version", SCHEMA_VERSION),
            "entries": entries,
        }
    except Exception as e:
        logger.warning(f"history: could not read file, starting fresh: {e}")
        return {"version": SCHEMA_VERSION, "entries": []}


def _write_raw(data: dict) -> None:
    """Write the history file atomically via a temp file + rename."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(HISTORY_FILE)
    except Exception as e:
        logger.error(f"history: could not write file: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


# ─── Public API ──────────────────────────────────────────────
def load() -> dict:
    """Return the raw structure (used by tests)."""
    return _read_raw()


def list_entries() -> list:
    """
    Return entries, newest first.

    Filters out non-dict entries, so a corrupt file with a mixed list
    (e.g. ["oops", 42, {...}]) does not crash the UI.
    """
    data = _read_raw()
    raw = data.get("entries", [])
    entries = [e for e in raw if isinstance(e, dict)]

    def _key(e):
        try:
            return float(e.get("finished_at", 0))
        except (TypeError, ValueError):
            return 0.0

    return sorted(entries, key=_key, reverse=True)


def count() -> int:
    """Number of entries currently stored."""
    return len(_read_raw().get("entries", []))


def add(
    source: str,
    output: str | None,
    duration: float | None,
    language: str | None,
    model: str | None,
    status: str,
    error: str | None = None,
) -> dict:
    """
    Append a new entry.

    status: 'ok' or 'error'. Anything else is stored as 'error'.
    Returns the created entry (with its generated id).
    """
    entry = {
        "id": str(uuid.uuid4()),
        "source": str(source) if source else "",
        "output": str(output) if output else "",
        "duration": float(duration) if duration is not None else None,
        "language": language or "",
        "model": model or "",
        "finished_at": time.time(),
        "status": status if status in ("ok", "error") else "error",
        "error": error or None,
    }

    data = _read_raw()
    entries = [e for e in data.get("entries", []) if isinstance(e, dict)]
    entries.insert(0, entry)

    # Trim to the cap, newest kept.
    if len(entries) > MAX_ENTRIES:
        entries = entries[:MAX_ENTRIES]

    data["entries"] = entries
    data["version"] = SCHEMA_VERSION
    _write_raw(data)

    return entry


def delete(entry_id: str) -> bool:
    """
    Remove one entry by id. Returns True if something was removed.
    """
    data = _read_raw()
    entries = [e for e in data.get("entries", []) if isinstance(e, dict)]
    new_entries = [e for e in entries if e.get("id") != entry_id]
    if len(new_entries) == len(entries):
        return False
    data["entries"] = new_entries
    _write_raw(data)
    return True


def clear() -> int:
    """
    Remove all entries. Returns the number of removed entries.
    """
    data = _read_raw()
    entries = [e for e in data.get("entries", []) if isinstance(e, dict)]
    n = len(entries)
    _write_raw({"version": SCHEMA_VERSION, "entries": []})
    return n
