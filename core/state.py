"""Глобальное состояние: флаг отмены и активные процессы."""
import threading
import time
import logging

logger = logging.getLogger(__name__)

CANCEL = threading.Event()
_ACTIVE_PROCS = set()
_ACTIVE_LOCK = threading.Lock()


def register_proc(p):
    with _ACTIVE_LOCK:
        _ACTIVE_PROCS.add(p)


def unregister_proc(p):
    with _ACTIVE_LOCK:
        _ACTIVE_PROCS.discard(p)


def kill_all_procs():
    with _ACTIVE_LOCK:
        procs = list(_ACTIVE_PROCS)
    if not procs:
        return
    logger.info(f"Убиваю {len(procs)} процессов…")
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    time.sleep(0.5)
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass


def request_cancel():
    CANCEL.set()
    kill_all_procs()


def reset_cancel():
    CANCEL.clear()