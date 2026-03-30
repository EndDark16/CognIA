import os
import sys
from email.message import EmailMessage

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import email_service
from config.settings import TestingConfig


def _env(name: str) -> str | None:
    return os.getenv(name)


@pytest.mark.skipif(os.getenv("SMTP_TEST_ENABLED") != "1", reason="SMTP_TEST_ENABLED not enabled")
def test_smtp_connection_integration():
    app = create_app(TestingConfig)
    with app.app_context():
        # This test sends a real email; it is opt-in only.
        host = _env("SMTP_HOST")
        port = _env("SMTP_PORT") or _env("SMTP_PORT__SSL") or _env("SMTP_PORT__TLS")
        user = _env("SMTP_USER")
        password = _env("SMTP_PASSWORD")
        from_addr = _env("EMAIL_FROM")
        to_addr = _env("TEST_SMTP_TO") or from_addr

        if not host or not port or not user or not password or not from_addr or not to_addr:
            pytest.skip("SMTP env vars not configured for integration test")

        app.config.update(
            SMTP_HOST=host,
            SMTP_PORT=int(port),
            SMTP_PORT_SSL=int(_env("SMTP_PORT__SSL") or 465),
            SMTP_PORT_TLS=int(_env("SMTP_PORT__TLS") or 587),
            SMTP_USER=user,
            SMTP_PASSWORD=password,
            SMTP_USE_TLS=_env("SMTP_USE_TLS").lower() == "true" if _env("SMTP_USE_TLS") else True,
            SMTP_USE_SSL=_env("SMTP_USE_SSL").lower() == "true" if _env("SMTP_USE_SSL") else False,
            SMTP_TIMEOUT=int(_env("SMTP_TIMEOUT") or 20),
        )

        msg = EmailMessage()
        msg["Subject"] = "SMTP integration test (CognIA)"
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.set_content("SMTP integration test message from CognIA backend.")

        email_service._send_via_smtp(msg)
