import os
import pickle
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, Tuple


class SimpleTTLCache:
    """Cache en memoria con TTL. No usar para secretos ni datos sensibles."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[Any, Tuple[Any, datetime]] = {}
        self._lock = Lock()

    def get(self, key: Any):
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            value, expires_at = item
            if expires_at < datetime.now(timezone.utc):
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Any, value: Any, ttl_seconds: int | None = None):
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: Any):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()


class CacheBackend:
    def get(self, key: str):
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear_prefix(self, prefix: str) -> None:
        raise NotImplementedError

    def backend_name(self) -> str:
        raise NotImplementedError


class InMemoryCacheBackend(CacheBackend):
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str):
        now = time.time()
        with self._lock:
            row = self._store.get(key)
            if not row:
                return None
            value, expires_at = row
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = time.time() + max(1, int(ttl_seconds))
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)

    def backend_name(self) -> str:
        return "memory"


class RedisCacheBackend(CacheBackend):
    def __init__(self, uri: str):
        import redis

        self._client = redis.from_url(uri)

    def get(self, key: str):
        raw = self._client.get(key)
        if raw is None:
            return None
        try:
            return pickle.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        self._client.setex(key, max(1, int(ttl_seconds)), payload)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def clear_prefix(self, prefix: str) -> None:
        try:
            for key in self._client.scan_iter(match=f"{prefix}*"):
                self._client.delete(key)
        except Exception:
            return

    def backend_name(self) -> str:
        return "redis"


_CACHE_BACKEND_LOCK = Lock()
_CACHE_BACKEND: CacheBackend = InMemoryCacheBackend()
_CACHE_KEY_PREFIX = "cognia"


def _normalize_cache_key(key: Any) -> str:
    if isinstance(key, str):
        return key
    return repr(key)


def cache_backend_info() -> dict[str, str]:
    with _CACHE_BACKEND_LOCK:
        return {
            "backend": _CACHE_BACKEND.backend_name(),
            "prefix": _CACHE_KEY_PREFIX,
        }


def init_cache_backend(cache_backend_uri: str | None = None, cache_key_prefix: str | None = None, logger=None) -> None:
    global _CACHE_BACKEND, _CACHE_KEY_PREFIX
    uri = (cache_backend_uri or "").strip() or os.getenv("CACHE_BACKEND_URI", "").strip()
    prefix = (cache_key_prefix or "").strip() or os.getenv("CACHE_KEY_PREFIX", "cognia").strip() or "cognia"

    chosen_backend: CacheBackend = InMemoryCacheBackend()
    backend_label = "memory"
    warning = None

    if uri and uri.startswith(("redis://", "rediss://")):
        try:
            chosen_backend = RedisCacheBackend(uri=uri)
            backend_label = "redis"
        except Exception as exc:
            warning = f"cache backend redis unavailable, fallback memory: {exc}"

    with _CACHE_BACKEND_LOCK:
        _CACHE_BACKEND = chosen_backend
        _CACHE_KEY_PREFIX = prefix

    if logger:
        logger.info("cache backend=%s prefix=%s", backend_label, prefix)
        if warning:
            logger.warning("%s", warning)


class NamespacedTTLCache:
    """TTL cache namespaced with pluggable backend (memory or Redis)."""

    def __init__(self, namespace: str, default_ttl_seconds: int = 300):
        self.namespace = namespace
        self.default_ttl = default_ttl_seconds

    def _full_key(self, key: Any) -> str:
        with _CACHE_BACKEND_LOCK:
            prefix = _CACHE_KEY_PREFIX
        return f"{prefix}:{self.namespace}:{_normalize_cache_key(key)}"

    def _prefix(self) -> str:
        with _CACHE_BACKEND_LOCK:
            prefix = _CACHE_KEY_PREFIX
        return f"{prefix}:{self.namespace}:"

    def get(self, key: Any):
        full_key = self._full_key(key)
        with _CACHE_BACKEND_LOCK:
            backend = _CACHE_BACKEND
        return backend.get(full_key)

    def set(self, key: Any, value: Any, ttl_seconds: int | None = None):
        ttl = max(1, int(ttl_seconds if ttl_seconds is not None else self.default_ttl))
        full_key = self._full_key(key)
        with _CACHE_BACKEND_LOCK:
            backend = _CACHE_BACKEND
        backend.set(full_key, value, ttl)

    def delete(self, key: Any):
        full_key = self._full_key(key)
        with _CACHE_BACKEND_LOCK:
            backend = _CACHE_BACKEND
        backend.delete(full_key)

    def clear(self):
        with _CACHE_BACKEND_LOCK:
            backend = _CACHE_BACKEND
        backend.clear_prefix(self._prefix())


# Caches compartidos backend
roles_cache = NamespacedTTLCache(namespace="roles", default_ttl_seconds=300)
user_security_cache = NamespacedTTLCache(namespace="user_security", default_ttl_seconds=45)
auth_me_cache = NamespacedTTLCache(namespace="auth_me", default_ttl_seconds=60)
qv2_active_version_cache = NamespacedTTLCache(namespace="qv2_active_version", default_ttl_seconds=120)
qv2_active_payload_cache = NamespacedTTLCache(namespace="qv2_active_payload", default_ttl_seconds=300)
qv2_activation_snapshot_cache = NamespacedTTLCache(namespace="qv2_activation_snapshot", default_ttl_seconds=300)
qv2_question_bank_cache = NamespacedTTLCache(namespace="qv2_question_bank", default_ttl_seconds=300)


def invalidate_roles_cache(user_id: Any) -> None:
    if user_id is None:
        return
    roles_cache.delete(user_id)
    roles_cache.delete(str(user_id))


def invalidate_user_security_cache(user_id: Any) -> None:
    if user_id is None:
        return
    user_security_cache.delete(user_id)
    user_security_cache.delete(str(user_id))


def invalidate_auth_me_cache(user_id: Any) -> None:
    if user_id is None:
        return
    auth_me_cache.delete(user_id)
    auth_me_cache.delete(str(user_id))


def invalidate_user_auth_caches(user_id: Any) -> None:
    invalidate_roles_cache(user_id)
    invalidate_user_security_cache(user_id)
    invalidate_auth_me_cache(user_id)
