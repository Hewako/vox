"""Кэш транскрипций и его автоматическая чистка."""
import logging
from config import CACHE_DIR, MAX_CACHE_MB

logger = logging.getLogger(__name__)


def cache_size_mb():
    if not CACHE_DIR.exists():
        return 0.0
    total = sum(p.stat().st_size for p in CACHE_DIR.glob("*.txt")
                if p.is_file())
    return total / (1024 * 1024)


def cleanup_cache(max_mb=MAX_CACHE_MB):
    """Удаляет самые старые файлы кэша, если размер превышает лимит."""
    if not CACHE_DIR.exists():
        return
    files = [p for p in CACHE_DIR.glob("*.txt") if p.is_file()]
    total = sum(p.stat().st_size for p in files) / (1024 * 1024)
    if total <= max_mb:
        return

    files.sort(key=lambda p: p.stat().st_mtime)
    removed = 0
    for p in files:
        if total <= max_mb:
            break
        size = p.stat().st_size / (1024 * 1024)
        try:
            p.unlink()
            total -= size
            removed += 1
        except Exception as e:
            logger.debug(f"Не удалось удалить {p}: {e}")
    if removed:
        logger.info(f"Кэш: удалено {removed} файлов, сейчас {total:.1f} МБ")


def clear_all_cache():
    """Удаляет все файлы кэша. Возвращает число удалённых."""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for p in CACHE_DIR.glob("*.txt"):
        try:
            p.unlink()
            removed += 1
        except Exception as e:
            logger.debug(f"Не удалось удалить {p}: {e}")
    if removed:
        logger.info(f"Кэш: очищен полностью, удалено {removed} файлов")
    return removed