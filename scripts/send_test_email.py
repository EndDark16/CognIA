import argparse
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"


def _bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() == "true"


def _int_env(name: str, default: int | None) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value) if str(value).isdigit() else default


def _resolve_smtp_mode(
    port: int | None,
    use_tls: bool,
    use_ssl: bool,
    port_ssl: int | None,
    port_tls: int | None,
):
    resolved_port = port
    if use_ssl and use_tls:
        if port_ssl and resolved_port == port_ssl:
            return resolved_port, False, True
        if port_tls and resolved_port == port_tls:
            return resolved_port, True, False
        if port_ssl:
            return port_ssl, False, True
        if port_tls:
            return port_tls, True, False
        return resolved_port, False, True
    if use_ssl:
        resolved_port = port_ssl or port
    if use_tls:
        resolved_port = port_tls or port
    return resolved_port, use_tls, use_ssl


def _render_template(template_name: str, context: dict) -> tuple[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html = env.get_template(f"{template_name}.html").render(**context)
    text = env.get_template(f"{template_name}.txt").render(**context)
    return html, text


def main() -> int:
    if load_dotenv:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Send a test email using templates.")
    parser.add_argument(
        "--template",
        default="welcome",
        help="Template base name (e.g., welcome, password_reset)",
    )
    parser.add_argument("--to", dest="to_email", help="Override TEST_SMTP_TO")
    parser.add_argument("--subject", help="Override email subject")
    parser.add_argument("--full-name", dest="full_name", default="CognIA User")
    parser.add_argument(
        "--reset-link",
        dest="reset_link",
        default="https://example.com/reset-password?token=test",
    )
    parser.add_argument(
        "--reject-reason",
        dest="reject_reason",
        default="Información insuficiente para validar la tarjeta profesional.",
    )
    args = parser.parse_args()

    host = os.getenv("SMTP_HOST")
    port = _int_env("SMTP_PORT", 587)
    port_ssl = _int_env("SMTP_PORT__SSL", None)
    port_tls = _int_env("SMTP_PORT__TLS", None)
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = _bool(os.getenv("SMTP_USE_TLS"))
    use_ssl = _bool(os.getenv("SMTP_USE_SSL"))
    timeout = int(os.getenv("SMTP_TIMEOUT", "10"))
    from_addr = os.getenv("EMAIL_FROM")
    to_addr = args.to_email or os.getenv("TEST_SMTP_TO") or parseaddr(from_addr or "")[1]

    if not host:
        print("Missing SMTP_HOST")
        return 1
    if not from_addr or "@" not in parseaddr(from_addr)[1]:
        print("EMAIL_FROM is missing or invalid")
        return 1
    if not to_addr or "@" not in parseaddr(to_addr)[1]:
        print("TEST_SMTP_TO/--to is missing or invalid")
        return 1

    port, use_tls, use_ssl = _resolve_smtp_mode(port, use_tls, use_ssl, port_ssl, port_tls)

    subject_map = {
        "welcome": "Bienvenido a CognIA",
        "password_reset": "Restablecer contraseña",
        "psychologist_rejected": "Verificación pendiente - CognIA",
    }
    subject = args.subject or subject_map.get(args.template, f"Test template: {args.template}")

    year_override = os.getenv("EMAIL_YEAR_OVERRIDE")
    context = {
        "user_name": args.full_name or "",
        "year": year_override or str(datetime.now(timezone.utc).year),
        "EMAIL_REPLY_TO": os.getenv("EMAIL_REPLY_TO") or "",
        "reset_link": args.reset_link,
        "reject_reason": args.reject_reason,
        "frontend_url": (os.getenv("FRONTEND_URL") or "").rstrip("/"),
        "asset_base_url": (os.getenv("EMAIL_ASSET_BASE_URL") or "").rstrip("/"),
        "logo_light_path": "logo/cognia-logo-light.png",
        "logo_dark_path": "logo/cognia-logo-dark.png",
        "signature_light_path": "logo/cognia-signature.png",
        "signature_dark_path": "logo/cognia-signature.png",
        "logo_path": "logo/cognia-logo-light.png",
        "signature_path": "logo/cognia-signature.png",
    }

    try:
        html_body, text_body = _render_template(args.template, context)
    except Exception as exc:
        print(f"Template render failed: {exc}")
        return 2

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    server = None
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
        server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.send_message(msg)
        print(f"OK: sent template '{args.template}' to {to_addr}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 3
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
