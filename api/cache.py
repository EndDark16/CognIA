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


# Cache de roles (TTL 5 min por defecto)
roles_cache = SimpleTTLCache(default_ttl_seconds=300)

# Cache corta para estado de seguridad JWT (iat vs password_changed_at/sessions_revoked_at)
user_security_cache = SimpleTTLCache(default_ttl_seconds=45)


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


def invalidate_user_auth_caches(user_id: Any) -> None:
    invalidate_roles_cache(user_id)
    invalidate_user_security_cache(user_id)
