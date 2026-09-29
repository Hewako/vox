"""Тесты для core.utils."""
from pathlib import Path

from core.utils import file_hash, atomic_write, fmt_time


def test_file_hash_consistent(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = file_hash(f)
    h2 = file_hash(f)
    assert h1 == h2
    assert len(h1) == 32  # md5 hex


def test_file_hash_changes(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello")
    f2.write_text("world")
    assert file_hash(f1) != file_hash(f2)


def test_atomic_write(tmp_path):
    p = tmp_path / "out.txt"
    atomic_write(p, "тест")
    assert p.read_text(encoding="utf-8") == "тест"
    # временного файла не должно остаться
    assert not Path(str(p) + ".tmp").exists()


def test_atomic_write_overwrites(tmp_path):
    p = tmp_path / "out.txt"
    p.write_text("старое")
    atomic_write(p, "новое")
    assert p.read_text(encoding="utf-8") == "новое"


def test_fmt_time_seconds():
    assert fmt_time(0) == "0:00"
    assert fmt_time(45) == "0:45"
    assert fmt_time(65) == "1:05"


def test_fmt_time_hours():
    assert fmt_time(3600) == "1:00:00"
    assert fmt_time(3725) == "1:02:05"


def test_fmt_time_negative():
    assert fmt_time(-10) == "0:00"