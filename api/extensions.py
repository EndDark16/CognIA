from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    # Keep storage configurable through app config (RATELIMIT_STORAGE_URI)
    # and environment defaults managed in config/settings.py.
    storage_uri=None,
)
