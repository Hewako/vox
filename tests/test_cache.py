"""Тесты для core.cache."""
import os
import time
import core.cache as cache_mod


def test_cache_size_mb_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    assert cache_mod.cache_size_mb() == 0.0


def test_cache_size_mb(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("x" * 1024)
    (tmp_path / "b.txt").write_text("y" * 2048)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    size = cache_mod.cache_size_mb()
    assert 0.002 < size < 0.01  # ~3 KB


def test_cleanup_cache_no_action_if_small(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("x" * 100)
    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)
    cache_mod.cleanup_cache(max_mb=10)
    assert (tmp_path / "a.txt").exists()


def test_cleanup_cache_removes_oldest(tmp_path, monkeypatch):
    # три файла по 200 КБ = ~0.59 МБ
    f1 = tmp_path / "old.txt"
    f2 = tmp_path / "mid.txt"
    f3 = tmp_path / "new.txt"
    for f in (f1, f2, f3):
        f.write_text("x" * (200 * 1024))

    # делаем их разными по времени изменения
    now = time.time()
    os.utime(f1, (now - 300, now - 300))
    os.utime(f2, (now - 200, now - 200))
    os.utime(f3, (now - 100, now - 100))

    monkeypatch.setattr(cache_mod, "CACHE_DIR", tmp_path)

    # лимит 0.25 МБ → должен удалить как минимум два самых старых
    cache_mod.cleanup_cache(max_mb=0.25)

    assert not f1.exists()
    assert not f2.exists()
    assert f3.exists()


def test_cleanup_cache_skips_nonexistent_dir(tmp_path, monkeypatch):
    fake = tmp_path / "no_such_dir"
    monkeypatch.setattr(cache_mod, "CACHE_DIR", fake)
    # не должно упасть
    cache_mod.cleanup_cache(max_mb=1)