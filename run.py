import os
import socket

from api.app import create_app

try:
    from werkzeug.debug import DebuggedApplication
    from werkzeug.serving import make_server, is_running_from_reloader
    from werkzeug._reloader import run_with_reloader
except Exception:  # pragma: no cover - fall back to app.run if Werkzeug import fails
    DebuggedApplication = None
    make_server = None
    is_running_from_reloader = None
    run_with_reloader = None


def _get_port() -> int:
    return int(os.getenv("PORT", "5000"))


def _should_reload(debug: bool) -> bool:
    return debug and os.getenv("FLASK_RUN_RELOAD", "true").lower() == "true"


def _wrap_debug(app):
    if DebuggedApplication is None or not app.debug:
        return app
    debugged = DebuggedApplication(app, evalex=True)
    for host in ("localhost", "127.0.0.1", "::1"):
        if host not in debugged.trusted_hosts:
            debugged.trusted_hosts.append(host)
    return debugged


def _run_dualstack(app, port: int, use_reloader: bool) -> bool:
    if make_server is None or is_running_from_reloader is None or run_with_reloader is None:
        return False
    if not socket.has_dualstack_ipv6():
        return False

    try:
        if is_running_from_reloader():
            fd = int(os.environ["WERKZEUG_SERVER_FD"])
        else:
            sock = socket.create_server(
                ("::", port),
                family=socket.AF_INET6,
                dualstack_ipv6=True,
            )
            sock.set_inheritable(True)
            fd = sock.fileno()
            sock.close()

        srv = make_server("::", port, _wrap_debug(app), threaded=True, fd=fd)
    except OSError:
        return False
    srv.socket.set_inheritable(True)
    os.environ["WERKZEUG_SERVER_FD"] = str(srv.fileno())

    if not is_running_from_reloader():
        srv.log_startup()

    if use_reloader:
        try:
            run_with_reloader(srv.serve_forever)
        finally:
            srv.server_close()
    else:
        srv.serve_forever()
    return True


app = create_app()

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = _get_port()
    use_reloader = _should_reload(app.debug)
    dualstack = os.getenv("DUALSTACK", "true").lower() == "true"

    if dualstack and _run_dualstack(app, port, use_reloader):
        raise SystemExit(0)

    app.run(host=host, port=port, debug=app.debug, use_reloader=use_reloader)
