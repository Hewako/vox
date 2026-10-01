"""Ядро транскрипции: ffmpeg + whisper-cli."""
import os
import re
import pty
import tempfile
import threading
import logging
import subprocess
from pathlib import Path

from config import (
    MODELS_DIR, CACHE_DIR, WHISPER_BIN, FFMPEG_BIN, VAD_MODEL,
)
from core.state import (
    CANCEL, register_proc, unregister_proc,
)
from core.utils import (
    get_duration, file_hash, atomic_write, DEVNULL,
)

logger = logging.getLogger(__name__)

SEG_RE = re.compile(r"\[(\d+):(\d+):(\d+)\.\d+\s+-->")

# Регулярка для строки автодетекта языка, которую пишет whisper-cli:
#   whisper_full_with_state: auto-detected language: ru (p = 0.987654)
LANG_RE = re.compile(
    r"auto-detected language:\s*([a-z]{2,3})\s*\(p\s*=\s*([\d.]+)\)",
    re.IGNORECASE,
)

def transcribe_one(media, model_name, language, use_vad,
                   save_srt=False, on_progress=None, on_status=None,
                   on_language=None, use_cache=True):
    """
    Транскрибирует один файл. Возвращает Path к .txt.

    Дополнительные callback'и:
      on_progress(x)              — прогресс 0..1
      on_status(msg)              — текущий этап
      on_language(code, prob)     — если было автоопределение, сообщает
                                    код языка и вероятность (0..1)
    """
    media = Path(media)
    on_progress = on_progress or (lambda x: None)
    on_status = on_status or (lambda m: None)
    on_language = on_language or (lambda code, prob: None)
    model_path = MODELS_DIR / model_name

    if CANCEL.is_set():
        raise RuntimeError("Отменено пользователем")

    cache_file = None
    if use_cache:
        key = f"{file_hash(media)}-{model_name}-{language}-{int(use_vad)}"
        cache_file = CACHE_DIR / f"{key}.txt"
        if cache_file.exists():
            on_status("Из кэша…")
            text = cache_file.read_text(encoding="utf-8")
            atomic_write(media.with_suffix(".txt"), text)
            on_progress(1.0)
            logger.info(f"[{media.name}] взято из кэша")
            return media.with_suffix(".txt")

    duration = get_duration(media)

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"

        on_status("Извлекаю аудио…")
        r = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(media),
             "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
            stdout=DEVNULL, stderr=DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg упал с кодом {r.returncode}")

        if CANCEL.is_set():
            raise RuntimeError("Отменено пользователем")

        on_status("Распознаю речь…")
        cmd = [WHISPER_BIN, "-m", str(model_path), "-f", str(wav),
               "-l", language, "-otxt"]
        if save_srt:
            cmd.append("-osrt")
        if use_vad and VAD_MODEL.exists():
            cmd.extend(["--vad", "-vm", str(VAD_MODEL)])

        logger.info(f"[{media.name}] whisper: {' '.join(cmd)}")

        master, slave = pty.openpty()
        proc = subprocess.Popen(cmd, stdout=slave, stderr=subprocess.PIPE)
        os.close(slave)
        register_proc(proc)

        stderr_chunks = []
        lang_reported = {"done": False}

        def read_err():
            try:
                while True:
                    chunk = proc.stderr.read(4096)
                    if not chunk:
                        break
                    stderr_chunks.append(chunk)

                    # Ищем строку про автоопределение языка
                    if not lang_reported["done"]:
                        text = chunk.decode("utf-8", errors="replace")
                        m = LANG_RE.search(text)
                        if m:
                            code = m.group(1).lower()
                            try:
                                prob = float(m.group(2))
                            except ValueError:
                                prob = 0.0
                            lang_reported["done"] = True
                            logger.info(
                                f"[{media.name}] определён язык: "
                                f"{code} ({prob:.2%})")
                            try:
                                on_language(code, prob)
                            except Exception as e:
                                logger.debug(f"on_language failed: {e}")
            except Exception:
                pass

        t = threading.Thread(target=read_err, daemon=True)
        t.start()

        buf = b""
        try:
            with os.fdopen(master, "rb", buffering=0) as f:
                while True:
                    if CANCEL.is_set():
                        break
                    try:
                        chunk = f.read(4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.rstrip(b"\r").decode(
                            "utf-8", errors="replace")
                        m = SEG_RE.search(line)
                        if m and duration:
                            h, mn, s = map(int, m.groups())
                            cur = h * 3600 + mn * 60 + s
                            on_progress(min(cur / duration, 0.99))
        finally:
            proc.wait()
            unregister_proc(proc)
            t.join(timeout=1)

        if CANCEL.is_set():
            raise RuntimeError("Отменено пользователем")

        if proc.returncode != 0:
            err_text = b"".join(stderr_chunks).decode(
                "utf-8", errors="replace")
            logger.error(f"[{media.name}] whisper-cli упал: "
                         f"code={proc.returncode}\n{err_text[-800:]}")
            raise RuntimeError(
                f"whisper-cli завершился с кодом {proc.returncode}\n"
                f"{err_text[-500:]}")

        # На случай, если язык не был отдан в потоке stderr —
        # попробуем вытащить из накопленного буфера.
        if not lang_reported["done"]:
            err_all = b"".join(stderr_chunks).decode(
                "utf-8", errors="replace")
            m = LANG_RE.search(err_all)
            if m:
                code = m.group(1).lower()
                try:
                    prob = float(m.group(2))
                except ValueError:
                    prob = 0.0
                try:
                    on_language(code, prob)
                except Exception:
                    pass

        produced = Path(str(wav) + ".txt")
        if not produced.exists():
            raise RuntimeError("Файл транскрипта не создан")

        text = produced.read_text(encoding="utf-8")
        if cache_file:
            cache_file.write_text(text, encoding="utf-8")

        atomic_write(media.with_suffix(".txt"), text)

        if save_srt:
            srt_src = Path(str(wav) + ".srt")
            if srt_src.exists():
                atomic_write(media.with_suffix(".srt"),
                             srt_src.read_text(encoding="utf-8"))
                logger.info(f"[{media.name}] SRT сохранён")

        on_progress(1.0)
        logger.info(f"[{media.name}] готово, {len(text)} символов")
        return media.with_suffix(".txt")