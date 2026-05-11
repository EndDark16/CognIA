import base64
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
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
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, int(ttl)))
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


class CacheBackendError(RuntimeError):
    """Backend-specific cache failure."""


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


def _serialize_cache_value(value: Any) -> str:
    def _default(obj):
        if isinstance(obj, datetime):
            return {"__cache_type__": "datetime", "value": obj.isoformat()}
        if isinstance(obj, date):
            return {"__cache_type__": "date", "value": obj.isoformat()}
        if isinstance(obj, uuid.UUID):
            return {"__cache_type__": "uuid", "value": str(obj)}
        if isinstance(obj, set):
            return {"__cache_type__": "set", "value": list(obj)}
        if isinstance(obj, tuple):
            return {"__cache_type__": "tuple", "value": list(obj)}
        if isinstance(obj, bytes):
            return {
                "__cache_type__": "bytes",
                "value": base64.b64encode(obj).decode("ascii"),
            }
        raise TypeError(f"type not serializable: {type(obj)!r}")

    return json.dumps(value, default=_default, ensure_ascii=True, separators=(",", ":"))


def _deserialize_cache_value(raw: str | bytes):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")

    def _hook(obj):
        type_tag = obj.get("__cache_type__")
        if not type_tag:
            return obj

        value = obj.get("value")
        if type_tag == "datetime":
            try:
                return datetime.fromisoformat(str(value))
            except Exception:
                return None
        if type_tag == "date":
            try:
                return date.fromisoformat(str(value))
            except Exception:
                return None
        if type_tag == "uuid":
            try:
                return uuid.UUID(str(value))
            except Exception:
                return None
        if type_tag == "set":
            try:
                return set(value or [])
            except Exception:
                return set()
        if type_tag == "tuple":
            try:
                return tuple(value or [])
            except Exception:
                return tuple()
        if type_tag == "bytes":
            try:
                return base64.b64decode(str(value).encode("ascii"))
            except Exception:
                return b""
        return obj

    return json.loads(raw, object_hook=_hook)


class RedisCacheBackend(CacheBackend):
    def __init__(
        self,
        uri: str,
        *,
        socket_timeout: float = 0.25,
        connect_timeout: float = 0.25,
        health_check_interval: int = 30,
    ):
        import redis

        self._client = redis.from_url(
            uri,
            decode_responses=False,
            socket_timeout=max(0.05, float(socket_timeout)),
            socket_connect_timeout=max(0.05, float(connect_timeout)),
            health_check_interval=max(0, int(health_check_interval)),
        )

    def get(self, key: str):
        try:
            raw = self._client.get(key)
        except Exception as exc:
            raise CacheBackendError(f"redis_get_failed:{exc}") from exc

        if raw is None:
            return None

        try:
            return _deserialize_cache_value(raw)
        except Exception as exc:
            raise CacheBackendError(f"redis_deserialize_failed:{exc}") from exc

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            payload = _serialize_cache_value(value)
            self._client.setex(key, max(1, int(ttl_seconds)), payload)
        except Exception as exc:
            raise CacheBackendError(f"redis_set_failed:{exc}") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception as exc:
            raise CacheBackendError(f"redis_delete_failed:{exc}") from exc

    def clear_prefix(self, prefix: str) -> None:
        try:
            for key in self._client.scan_iter(match=f"{prefix}*"):
                self._client.delete(key)
        except Exception as exc:
            raise CacheBackendError(f"redis_clear_failed:{exc}") from exc

    def backend_name(self) -> str:
        return "redis"


_CACHE_BACKEND_LOCK = Lock()
_CACHE_METRICS_LOCK = Lock()

_CACHE_BACKEND: CacheBackend = InMemoryCacheBackend()
_CACHE_FALLBACK_BACKEND: CacheBackend = InMemoryCacheBackend()
_CACHE_KEY_PREFIX = "cognia"
_CACHE_FAIL_OPEN = True
_CACHE_BACKEND_REQUIRED = False
_CACHE_DEFAULT_TTL_SECONDS = 300
_CACHE_REDIS_CONFIGURED = False
_CACHE_REDIS_AVAILABLE = False
_CACHE_LAST_WARNING = ""

_CACHE_METRICS: dict[str, Any] = {
    "get_hits": 0,
    "get_misses": 0,
    "get_errors": 0,
    "set_errors": 0,
    "delete_errors": 0,
    "clear_errors": 0,
    "fallback_uses": 0,
    "namespace_hits": defaultdict(int),
    "namespace_misses": defaultdict(int),
}


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_from_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except Exception:
        return default


def _float_from_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except Exception:
        return default


def _normalize_cache_key(key: Any) -> str:
    if isinstance(key, str):
        return key
    return repr(key)


def _record_cache_hit(namespace: str) -> None:
    with _CACHE_METRICS_LOCK:
        _CACHE_METRICS["get_hits"] += 1
        _CACHE_METRICS["namespace_hits"][namespace] += 1


def _record_cache_miss(namespace: str) -> None:
    with _CACHE_METRICS_LOCK:
        _CACHE_METRICS["get_misses"] += 1
        _CACHE_METRICS["namespace_misses"][namespace] += 1


def _record_cache_error(error_bucket: str) -> None:
    with _CACHE_METRICS_LOCK:
        if error_bucket in _CACHE_METRICS:
            _CACHE_METRICS[error_bucket] += 1


def _record_cache_fallback() -> None:
    with _CACHE_METRICS_LOCK:
        _CACHE_METRICS["fallback_uses"] += 1


def cache_metrics_snapshot() -> dict[str, Any]:
    with _CACHE_METRICS_LOCK:
        return {
            "get_hits": int(_CACHE_METRICS["get_hits"]),
            "get_misses": int(_CACHE_METRICS["get_misses"]),
            "get_errors": int(_CACHE_METRICS["get_errors"]),
            "set_errors": int(_CACHE_METRICS["set_errors"]),
            "delete_errors": int(_CACHE_METRICS["delete_errors"]),
            "clear_errors": int(_CACHE_METRICS["clear_errors"]),
            "fallback_uses": int(_CACHE_METRICS["fallback_uses"]),
            "namespace_hits": {
                str(key): int(value)
                for key, value in dict(_CACHE_METRICS["namespace_hits"]).items()
            },
            "namespace_misses": {
                str(key): int(value)
                for key, value in dict(_CACHE_METRICS["namespace_misses"]).items()
            },
        }


def cache_backend_info() -> dict[str, Any]:
    with _CACHE_BACKEND_LOCK:
        return {
            "backend": _CACHE_BACKEND.backend_name(),
            "prefix": _CACHE_KEY_PREFIX,
            "fail_open": bool(_CACHE_FAIL_OPEN),
            "required": bool(_CACHE_BACKEND_REQUIRED),
            "default_ttl_seconds": int(_CACHE_DEFAULT_TTL_SECONDS),
            "redis_configured": bool(_CACHE_REDIS_CONFIGURED),
            "redis_available": bool(_CACHE_REDIS_AVAILABLE),
            "last_warning": _CACHE_LAST_WARNING,
        }


def init_cache_backend(
    cache_backend_uri: str | None = None,
    cache_key_prefix: str | None = None,
    cache_backend_required: bool | None = None,
    cache_default_ttl_seconds: int | None = None,
    cache_fail_open: bool | None = None,
    cache_redis_socket_timeout: float | None = None,
    cache_redis_connect_timeout: float | None = None,
    logger=None,
) -> None:
    global _CACHE_BACKEND
    global _CACHE_KEY_PREFIX
    global _CACHE_FAIL_OPEN
    global _CACHE_BACKEND_REQUIRED
    global _CACHE_DEFAULT_TTL_SECONDS
    global _CACHE_REDIS_CONFIGURED
    global _CACHE_REDIS_AVAILABLE
    global _CACHE_LAST_WARNING

    uri = (cache_backend_uri or "").strip() or os.getenv("CACHE_BACKEND_URI", "").strip()
    prefix = (
        (cache_key_prefix or "").strip()
        or os.getenv("CACHE_KEY_PREFIX", "cognia").strip()
        or "cognia"
    )
    required = (
        bool(cache_backend_required)
        if cache_backend_required is not None
        else _bool_from_env("CACHE_BACKEND_REQUIRED", False)
    )
    fail_open = (
        bool(cache_fail_open)
        if cache_fail_open is not None
        else _bool_from_env("CACHE_FAIL_OPEN", True)
    )
    default_ttl = (
        max(1, int(cache_default_ttl_seconds))
        if cache_default_ttl_seconds is not None
        else max(1, _int_from_env("CACHE_DEFAULT_TTL_SECONDS", 300))
    )
    redis_socket_timeout = (
        float(cache_redis_socket_timeout)
        if cache_redis_socket_timeout is not None
        else _float_from_env("CACHE_REDIS_SOCKET_TIMEOUT", 0.25)
    )
    redis_connect_timeout = (
        float(cache_redis_connect_timeout)
        if cache_redis_connect_timeout is not None
        else _float_from_env("CACHE_REDIS_CONNECT_TIMEOUT", 0.25)
    )

    chosen_backend: CacheBackend = InMemoryCacheBackend()
    warning = ""
    redis_configured = bool(uri and uri.startswith(("redis://", "rediss://")))
    redis_available = False

    if required and not redis_configured:
        raise RuntimeError("CACHE_BACKEND_REQUIRED=true but CACHE_BACKEND_URI is not configured")

    if redis_configured:
        try:
            chosen_backend = RedisCacheBackend(
                uri=uri,
                socket_timeout=redis_socket_timeout,
                connect_timeout=redis_connect_timeout,
            )
            redis_available = True
        except Exception as exc:
            warning = f"cache backend redis unavailable, fallback memory: {exc}"
            if required:
                raise RuntimeError(warning) from exc

    with _CACHE_BACKEND_LOCK:
        _CACHE_BACKEND = chosen_backend
        _CACHE_KEY_PREFIX = prefix
        _CACHE_FAIL_OPEN = fail_open
        _CACHE_BACKEND_REQUIRED = required
        _CACHE_DEFAULT_TTL_SECONDS = default_ttl
        _CACHE_REDIS_CONFIGURED = redis_configured
        _CACHE_REDIS_AVAILABLE = redis_available
        _CACHE_LAST_WARNING = warning

        # Keep namespace defaults aligned when global default is explicitly configured.
        roles_cache.default_ttl = max(1, default_ttl)
        qv2_question_bank_cache.default_ttl = max(1, default_ttl)

    if logger:
        backend_label = chosen_backend.backend_name()
        logger.info(
            "cache backend=%s prefix=%s required=%s fail_open=%s redis_configured=%s redis_available=%s",
            backend_label,
            prefix,
            required,
            fail_open,
            redis_configured,
            redis_available,
        )
        if warning:
            logger.warning("%s", warning)


def _run_with_fallback(op_name: str, fn, fallback_fn):
    with _CACHE_BACKEND_LOCK:
        fail_open = _CACHE_FAIL_OPEN

    try:
        return fn()
    except Exception:
        _record_cache_error(f"{op_name}_errors")
        if not fail_open:
            raise
        _record_cache_fallback()
        try:
            return fallback_fn()
        except Exception:
            return None


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

        def _primary_get():
            with _CACHE_BACKEND_LOCK:
                backend = _CACHE_BACKEND
            return backend.get(full_key)

        def _fallback_get():
            return _CACHE_FALLBACK_BACKEND.get(full_key)

        value = _run_with_fallback("get", _primary_get, _fallback_get)
        if value is None:
            _record_cache_miss(self.namespace)
        else:
            _record_cache_hit(self.namespace)
        return value

    def set(self, key: Any, value: Any, ttl_seconds: int | None = None):
        ttl = max(1, int(ttl_seconds if ttl_seconds is not None else self.default_ttl))
        full_key = self._full_key(key)

        def _primary_set():
            with _CACHE_BACKEND_LOCK:
                backend = _CACHE_BACKEND
            backend.set(full_key, value, ttl)

        def _fallback_set():
            _CACHE_FALLBACK_BACKEND.set(full_key, value, ttl)

        _run_with_fallback("set", _primary_set, _fallback_set)

    def delete(self, key: Any):
        full_key = self._full_key(key)

        def _primary_delete():
            with _CACHE_BACKEND_LOCK:
                backend = _CACHE_BACKEND
            backend.delete(full_key)

        def _fallback_delete():
            _CACHE_FALLBACK_BACKEND.delete(full_key)

        _run_with_fallback("delete", _primary_delete, _fallback_delete)

    def clear(self):
        prefix = self._prefix()

        def _primary_clear():
            with _CACHE_BACKEND_LOCK:
                backend = _CACHE_BACKEND
            backend.clear_prefix(prefix)

        def _fallback_clear():
            _CACHE_FALLBACK_BACKEND.clear_prefix(prefix)

        _run_with_fallback("clear", _primary_clear, _fallback_clear)


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
