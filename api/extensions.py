import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Permite configurar un backend de almacenamiento para rate limits (p.ej. Redis)
_storage_uri = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
)
