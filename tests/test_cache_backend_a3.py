import os
import sys
from datetime import datetime, timezone

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import api.cache as cache


class _ExplodingBackend(cache.CacheBackend):
    def get(self, key: str):
        raise cache.CacheBackendError("boom_get")

    def set(self, key: str, value, ttl_seconds: int) -> None:
        raise cache.CacheBackendError("boom_set")

    def delete(self, key: str) -> None:
        raise cache.CacheBackendError("boom_delete")

    def clear_prefix(self, prefix: str) -> None:
        raise cache.CacheBackendError("boom_clear")

    def backend_name(self) -> str:
        return "exploding"


class _RedisUnavailable:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("redis unavailable")


def test_cache_backend_memory_and_metrics_roundtrip():
    cache.init_cache_backend(
        cache_backend_uri="",
        cache_key_prefix="testcache",
        cache_fail_open=True,
        cache_default_ttl_seconds=30,
    )
    ns = cache.NamespacedTTLCache(namespace="a3_test", default_ttl_seconds=30)
    ns.clear()

    ns.set("key", {"ts": datetime.now(timezone.utc).isoformat()}, ttl_seconds=10)
    assert ns.get("key") is not None
    assert ns.get("missing") is None

    snapshot = cache.cache_metrics_snapshot()
    assert snapshot["get_hits"] >= 1
    assert snapshot["get_misses"] >= 1
    assert snapshot["namespace_hits"].get("a3_test", 0) >= 1


def test_cache_backend_redis_unavailable_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(cache, "RedisCacheBackend", _RedisUnavailable)
    cache.init_cache_backend(
        cache_backend_uri="redis://localhost:6379/0",
        cache_key_prefix="testcache",
        cache_fail_open=True,
        cache_backend_required=False,
    )
    info = cache.cache_backend_info()
    assert info["backend"] == "memory"
    assert info["redis_configured"] is True
    assert info["redis_available"] is False
    assert "fallback" in str(info.get("last_warning", "")).lower()


def test_cache_backend_required_raises_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(cache, "RedisCacheBackend", _RedisUnavailable)
    with pytest.raises(RuntimeError):
        cache.init_cache_backend(
            cache_backend_uri="redis://localhost:6379/0",
            cache_key_prefix="testcache",
            cache_backend_required=True,
            cache_fail_open=False,
        )


def test_namespaced_cache_fail_open_uses_fallback_memory(monkeypatch):
    cache.init_cache_backend(
        cache_backend_uri="",
        cache_key_prefix="testcache",
        cache_fail_open=True,
        cache_default_ttl_seconds=30,
    )
    try:
        with cache._CACHE_BACKEND_LOCK:  # noqa: SLF001 - intentional for behavior verification
            cache._CACHE_BACKEND = _ExplodingBackend()  # noqa: SLF001

        ns = cache.NamespacedTTLCache(namespace="a3_fail_open", default_ttl_seconds=30)
        ns.clear()
        ns.set("k", "v", ttl_seconds=10)
        assert ns.get("k") == "v"

        metrics = cache.cache_metrics_snapshot()
        assert metrics["fallback_uses"] >= 2
    finally:
        cache.init_cache_backend(
            cache_backend_uri="",
            cache_key_prefix="testcache",
            cache_fail_open=True,
            cache_default_ttl_seconds=30,
        )
