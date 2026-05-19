"""Tests for the Redis cache helper.

Forces the cache client to None via monkeypatch so we can exercise the
graceful-degrade paths without spinning up a real Redis.
"""
from __future__ import annotations

import app.services.cache as cache_module


def test_get_or_set_calls_loader_when_redis_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "get_client", lambda: None)
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"x": 42}

    out1 = cache_module.get_or_set("k1", loader)
    out2 = cache_module.get_or_set("k1", loader)
    # Without redis, every call hits the loader (no caching).
    assert out1 == {"x": 42}
    assert out2 == {"x": 42}
    assert calls["n"] == 2


def test_invalidate_returns_zero_when_redis_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "get_client", lambda: None)
    assert cache_module.invalidate("any:") == 0


def test_get_or_set_loader_exception_propagates(monkeypatch) -> None:
    monkeypatch.setattr(cache_module, "get_client", lambda: None)

    def loader():
        raise RuntimeError("boom")

    try:
        cache_module.get_or_set("k", loader)
    except RuntimeError as e:
        assert str(e) == "boom"
    else:
        raise AssertionError("expected RuntimeError")
