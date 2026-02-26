import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

from flask import current_app, render_template

from app.models import EmailDeliveryLog, db
from api.services.unsubscribe_service import generate_unsubscribe_token


def _build_list_unsubscribe_header(to_email: str) -> tuple[str | None, bool]:
    items = []
    list_unsub = current_app.config.get("EMAIL_LIST_UNSUBSCRIBE")
    if list_unsub:
        items.append(list_unsub)

    base_url = current_app.config.get("EMAIL_UNSUBSCRIBE_URL")
    if base_url:
        token = generate_unsubscribe_token(to_email)
        if token:
            separator = "&" if "?" in base_url else "?"
            url = f"{base_url}{separator}token={token}"
            items.append(f"<{url}>")
        else:
            current_app.logger.warning("EMAIL_UNSUBSCRIBE_URL set but token could not be generated")

    if not items:
        return None, False
    return ", ".join(items), any(item.startswith("<http") or item.startswith("http") for item in items)


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
    list_unsub, has_url = _build_list_unsubscribe_header(to_email)
    if list_unsub:
        msg["List-Unsubscribe"] = list_unsub
        if has_url:
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _resolve_smtp_mode(
    host: str,
    port: int | None,
    use_tls: bool,
    use_ssl: bool,
    port_ssl: int | None,
    port_tls: int | None,
) -> tuple[int | None, bool, bool]:
    resolved_port = port
    if use_ssl and use_tls:
        if port_ssl and resolved_port == port_ssl:
            current_app.logger.info("SMTP: both TLS/SSL enabled; using SSL for SSL port")
            return resolved_port, False, True
        if port_tls and resolved_port == port_tls:
            current_app.logger.info("SMTP: both TLS/SSL enabled; using TLS for TLS port")
            return resolved_port, True, False
        if port_ssl:
            current_app.logger.warning("SMTP: both TLS/SSL enabled; defaulting to SSL port")
            return port_ssl, False, True
        if port_tls:
            current_app.logger.warning("SMTP: both TLS/SSL enabled; defaulting to TLS port")
            return port_tls, True, False
        current_app.logger.warning("SMTP: both TLS/SSL enabled; using SMTP_PORT fallback")
        return resolved_port, False, True
    if use_ssl:
        resolved_port = port_ssl or port
    if use_tls:
        resolved_port = port_tls or port
    return resolved_port, use_tls, use_ssl


def _send_via_smtp(message: EmailMessage) -> None:
    host = current_app.config.get("SMTP_HOST")
    port = current_app.config.get("SMTP_PORT")
    port_ssl = current_app.config.get("SMTP_PORT_SSL")
    port_tls = current_app.config.get("SMTP_PORT_TLS")
    user = current_app.config.get("SMTP_USER")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = current_app.config.get("SMTP_USE_TLS")
    use_ssl = current_app.config.get("SMTP_USE_SSL")
    timeout = current_app.config.get("SMTP_TIMEOUT", 10)

    if not host:
        raise RuntimeError("SMTP_HOST is not configured")

    port, use_tls, use_ssl = _resolve_smtp_mode(host, port, use_tls, use_ssl, port_ssl, port_tls)

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
    asset_base_url = (current_app.config.get("EMAIL_ASSET_BASE_URL") or "").rstrip("/")
    frontend_url = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    html_body = render_template(
        "email/welcome.html",
        user_name=full_name or "usuario",
        year=datetime.now(timezone.utc).year,
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
        asset_base_url=asset_base_url,
        frontend_url=frontend_url,
        logo_light_path="logo/cognia-logo-light.png",
        logo_dark_path="logo/cognia-logo-dark.png",
        signature_light_path="logo/cognia-signature.png",
        signature_dark_path="logo/cognia-signature.png",
    )
    text_body = render_template(
        "email/welcome.txt",
        user_name=full_name or "usuario",
        year=datetime.now(timezone.utc).year,
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
        frontend_url=frontend_url,
    )
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
    asset_base_url = (current_app.config.get("EMAIL_ASSET_BASE_URL") or "").rstrip("/")
    html_body = render_template(
        "email/password_reset.html",
        full_name=full_name or "",
        reset_link=reset_link,
        asset_base_url=asset_base_url,
        logo_path="logo/cognia-logo-light.png",
        logo_light_path="logo/cognia-logo-light.png",
        logo_dark_path="logo/cognia-logo-dark.png",
        signature_path="logo/cognia-signature.png",
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
    )
    text_body = render_template(
        "email/password_reset.txt",
        full_name=full_name or "",
        reset_link=reset_link,
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
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


def send_psychologist_rejected_email(*, to_email: str, full_name: str | None, reject_reason: str):
    subject = "Verificación pendiente - CognIA"
    asset_base_url = (current_app.config.get("EMAIL_ASSET_BASE_URL") or "").rstrip("/")
    html_body = render_template(
        "email/psychologist_rejected.html",
        user_name=full_name or "usuario",
        reject_reason=reject_reason,
        year=datetime.now(timezone.utc).year,
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
        asset_base_url=asset_base_url,
        logo_light_path="logo/cognia-logo-light.png",
        logo_dark_path="logo/cognia-logo-dark.png",
        signature_light_path="logo/cognia-signature.png",
        signature_dark_path="logo/cognia-signature.png",
    )
    text_body = render_template(
        "email/psychologist_rejected.txt",
        user_name=full_name or "usuario",
        reject_reason=reject_reason,
        year=datetime.now(timezone.utc).year,
        EMAIL_REPLY_TO=current_app.config.get("EMAIL_REPLY_TO") or "soporte@cognia.app",
    )
    if current_app.config.get("EMAIL_SEND_ASYNC", True):
        send_email_async(
            template="psychologist_rejected",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )
    else:
        send_email(
            template="psychologist_rejected",
            subject=subject,
            to_email=to_email,
            html_body=html_body,
            text_body=text_body,
        )
