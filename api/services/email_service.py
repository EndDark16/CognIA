import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

from flask import current_app, render_template

from app.models import EmailDeliveryLog, db


def _build_message(*, subject: str, to_email: str, html_body: str, text_body: str) -> EmailMessage:
    from_addr = current_app.config.get("EMAIL_FROM")
    if not from_addr or "@" not in parseaddr(from_addr)[1]:
        raise RuntimeError("EMAIL_FROM is not configured or invalid")
    if not to_email or "@" not in parseaddr(to_email)[1]:
        raise RuntimeError("Recipient email is invalid")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = to_email
    msg["From"] = from_addr
    reply_to = current_app.config.get("EMAIL_REPLY_TO")
    if reply_to:
        msg["Reply-To"] = reply_to
    list_unsub = current_app.config.get("EMAIL_LIST_UNSUBSCRIBE")
    if list_unsub:
        msg["List-Unsubscribe"] = list_unsub
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _send_via_smtp(message: EmailMessage) -> None:
    host = current_app.config.get("SMTP_HOST")
    port = current_app.config.get("SMTP_PORT")
    user = current_app.config.get("SMTP_USER")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = current_app.config.get("SMTP_USE_TLS")
    use_ssl = current_app.config.get("SMTP_USE_SSL")
    timeout = current_app.config.get("SMTP_TIMEOUT", 10)

    if not host:
        raise RuntimeError("SMTP_HOST is not configured")

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)

    try:
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _log_delivery(template: str, to_email: str, subject: str, status: str, error_message: str | None = None):
    log = EmailDeliveryLog(
        template=template,
        recipient_email=to_email,
        subject=subject,
        status=status,
        error_message=error_message,
        sent_at=datetime.now(timezone.utc) if status == "sent" else None,
    )
    db.session.add(log)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def send_email(*, template: str, subject: str, to_email: str, html_body: str, text_body: str) -> None:
    if not current_app.config.get("EMAIL_ENABLED", False):
        current_app.logger.info("Email disabled; skipping %s to %s", template, to_email)
        return

    if current_app.config.get("EMAIL_SANDBOX", False):
        current_app.logger.info("Email sandbox enabled; logging only (%s to %s)", template, to_email)
        _log_delivery(template, to_email, subject, "sandboxed")
        return

    message = _build_message(
        subject=subject,
        to_email=to_email,
        html_body=html_body,
        text_body=text_body,
    )

    try:
        _send_via_smtp(message)
        _log_delivery(template, to_email, subject, "sent")
    except Exception as exc:
        current_app.logger.error("Email send failed (%s -> %s): %s", template, to_email, exc, exc_info=True)
        try:
            _log_delivery(template, to_email, subject, "failed", str(exc))
        except Exception:
            db.session.rollback()


def send_email_async(*, template: str, subject: str, to_email: str, html_body: str, text_body: str) -> None:
    app = current_app._get_current_object()

    def _runner():
        with app.app_context():
            send_email(
                template=template,
                subject=subject,
                to_email=to_email,
                html_body=html_body,
                text_body=text_body,
            )

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()


def send_welcome_email(*, to_email: str, full_name: str | None):
    subject = "Bienvenido a CognIA"
    html_body = render_template("email/welcome.html", full_name=full_name or "")
    text_body = render_template("email/welcome.txt", full_name=full_name or "")
    if current_app.config.get("EMAIL_SEND_ASYNC", True):
        send_email_async(
            template="welcome",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )
    else:
        send_email(
            template="welcome",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )


def send_password_reset(*, to_email: str, reset_link: str, full_name: str | None):
    subject = "Restablecer contraseña"
    html_body = render_template(
        "email/password_reset.html",
        full_name=full_name or "",
        reset_link=reset_link,
    )
    text_body = render_template(
        "email/password_reset.txt",
        full_name=full_name or "",
        reset_link=reset_link,
    )
    if current_app.config.get("EMAIL_SEND_ASYNC", True):
        send_email_async(
            template="password_reset",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )
    else:
        send_email(
            template="password_reset",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )
