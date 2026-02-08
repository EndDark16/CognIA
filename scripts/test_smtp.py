import os
import sys
import smtplib
from email.message import EmailMessage
from email.utils import parseaddr

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def _bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() == "true"


def _int_env(name: str, default: int | None) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value) if str(value).isdigit() else default


def main() -> int:
    if load_dotenv:
        load_dotenv()

    host = os.getenv("SMTP_HOST")
    port = _int_env("SMTP_PORT", 0) or 0
    port_ssl = _int_env("SMTP_PORT__SSL", None)
    port_tls = _int_env("SMTP_PORT__TLS", None)
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = _bool(os.getenv("SMTP_USE_TLS"))
    use_ssl = _bool(os.getenv("SMTP_USE_SSL"))
    timeout = int(os.getenv("SMTP_TIMEOUT", "10") or 10)
    from_addr = os.getenv("EMAIL_FROM")
    to_addr = os.getenv("TEST_SMTP_TO") or parseaddr(from_addr)[1]

    if not host or not port:
        print("Missing SMTP_HOST or SMTP_PORT")
        return 1
    if not from_addr or "@" not in parseaddr(from_addr)[1]:
        print("EMAIL_FROM is missing or invalid")
        return 1
    if not to_addr or "@" not in parseaddr(to_addr)[1]:
        print("TEST_SMTP_TO or EMAIL_FROM must be a valid email")
        return 1
    if use_tls and use_ssl:
        if port_ssl and port == port_ssl:
            use_tls = False
        elif port_tls and port == port_tls:
            use_ssl = False
        elif port_ssl:
            port = port_ssl
            use_tls = False
        elif port_tls:
            port = port_tls
            use_ssl = False
        else:
            use_tls = False
    if use_ssl:
        port = port_ssl or port
    if use_tls:
        port = port_tls or port

    msg = EmailMessage()
    msg["Subject"] = "SMTP test (CognIA)"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content("SMTP test message from CognIA backend.")

    server = None
    try:
        debug = _bool(os.getenv("SMTP_DEBUG"))
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(timeout=timeout)

        if debug:
            server.set_debuglevel(1)
            print("DEBUG: connecting...")

        if not use_ssl:
            server.connect(host, port)
        if debug:
            print("DEBUG: connected, sending EHLO...")

        server.ehlo()
        if debug:
            print("DEBUG: EHLO ok")
        if use_tls and not use_ssl:
            if debug:
                print("DEBUG: starting TLS...")
            server.starttls()
            server.ehlo()
            if debug:
                print("DEBUG: TLS ok")
        if user and password:
            if debug:
                print("DEBUG: logging in...")
            server.login(user, password)
            if debug:
                print("DEBUG: login ok")
        server.send_message(msg)
        print(f"OK: sent to {to_addr} via {host}:{port} (TLS={use_tls}, SSL={use_ssl})")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 2
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
