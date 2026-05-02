import os
import sys
from email.message import EmailMessage
from urllib.parse import urlparse, parse_qs

import pytest

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from api.services import email_service
from api.services.unsubscribe_service import verify_unsubscribe_token
from app.models import db, EmailDeliveryLog
from config.settings import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_build_message_includes_headers(app):
    with app.app_context():
        app.config.update(
            EMAIL_FROM="CognIA <no-reply@example.com>",
            EMAIL_REPLY_TO="soporte@example.com",
            EMAIL_LIST_UNSUBSCRIBE="<mailto:unsubscribe@example.com>",
        )
        msg = email_service._build_message(
            subject="Test",
            to_email="user@example.com",
            html_body="<p>Hola</p>",
            text_body="Hola",
        )
        assert msg["From"] == "CognIA <no-reply@example.com>"
        assert msg["Reply-To"] == "soporte@example.com"
        assert msg["List-Unsubscribe"] == "<mailto:unsubscribe@example.com>"


def test_list_unsubscribe_url_includes_signed_token(app):
    with app.app_context():
        app.config.update(
            EMAIL_FROM="CognIA <no-reply@example.com>",
            EMAIL_UNSUBSCRIBE_URL="https://api.example.com/api/email/unsubscribe",
            EMAIL_UNSUBSCRIBE_SECRET="secret-key",
        )
        msg = email_service._build_message(
            subject="Test",
            to_email="user@example.com",
            html_body="<p>Hola</p>",
            text_body="Hola",
        )
        header = msg["List-Unsubscribe"]
        assert header is not None
        url = header.strip("<>")
        token = parse_qs(urlparse(url).query).get("token", [None])[0]
        assert token
        assert verify_unsubscribe_token(token) == "user@example.com"
        assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_send_email_sandbox_logs(app):
    with app.app_context():
        app.config.update(
            EMAIL_ENABLED=True,
            EMAIL_SANDBOX=True,
            EMAIL_FROM="CognIA <no-reply@example.com>",
        )
        email_service.send_email(
            template="welcome",
            subject="Test",
            to_email="user@example.com",
            html_body="<p>Hola</p>",
            text_body="Hola",
        )
        entry = EmailDeliveryLog.query.filter_by(template="welcome").first()
        assert entry is not None
        assert entry.status == "sandboxed"


def test_send_email_disabled_no_log(app):
    with app.app_context():
        app.config.update(
            EMAIL_ENABLED=False,
            EMAIL_SANDBOX=False,
            EMAIL_FROM="CognIA <no-reply@example.com>",
        )
        email_service.send_email(
            template="welcome",
            subject="Test",
            to_email="user@example.com",
            html_body="<p>Hola</p>",
            text_body="Hola",
        )
        entry = EmailDeliveryLog.query.filter_by(template="welcome").first()
        assert entry is None


def test_send_via_smtp_tls(monkeypatch, app):
    created = {}

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.actions = []
            created["plain"] = self

        def ehlo(self):
            self.actions.append("ehlo")

        def starttls(self):
            self.actions.append("starttls")

        def login(self, user, password):
            self.actions.append(("login", user, password))

        def send_message(self, message):
            self.actions.append("send")

        def quit(self):
            self.actions.append("quit")

    monkeypatch.setattr(email_service.smtplib, "SMTP", DummySMTP)

    with app.app_context():
        app.config.update(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=465,
            SMTP_PORT_TLS=587,
            SMTP_PORT_SSL=465,
            SMTP_USER="user",
            SMTP_PASSWORD="pass",
            SMTP_USE_TLS=True,
            SMTP_USE_SSL=False,
        )
        msg = EmailMessage()
        msg["Subject"] = "Test"
        email_service._send_via_smtp(msg)

    inst = created["plain"]
    assert inst.host == "smtp.example.com"
    assert inst.port == 587
    assert "starttls" in inst.actions
    assert ("login", "user", "pass") in inst.actions


def test_send_via_smtp_ssl(monkeypatch, app):
    created = {}

    class DummySMTPSSL:
        def __init__(self, host, port, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.actions = []
            created["ssl"] = self

        def ehlo(self):
            self.actions.append("ehlo")

        def login(self, user, password):
            self.actions.append(("login", user, password))

        def send_message(self, message):
            self.actions.append("send")

        def quit(self):
            self.actions.append("quit")

    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", DummySMTPSSL)

    with app.app_context():
        app.config.update(
            SMTP_HOST="smtp.example.com",
            SMTP_PORT=465,
            SMTP_PORT_TLS=587,
            SMTP_PORT_SSL=465,
            SMTP_USER="user",
            SMTP_PASSWORD="pass",
            SMTP_USE_TLS=True,
            SMTP_USE_SSL=True,
        )
        msg = EmailMessage()
        msg["Subject"] = "Test"
        email_service._send_via_smtp(msg)

    inst = created["ssl"]
    assert inst.host == "smtp.example.com"
    assert inst.port == 465
