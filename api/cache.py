from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple


class SimpleTTLCache:
    """Cache en memoria con TTL. No usar para secretos ni datos sensibles."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._store: Dict[Any, Tuple[Any, datetime]] = {}

    def get(self, key: Any):
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
        self._store[key] = (value, expires_at)

    def clear(self):
        self._store.clear()


# Cache de roles (TTL 5 min por defecto)
roles_cache = SimpleTTLCache(default_ttl_seconds=300)
