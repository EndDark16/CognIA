# api/app.py

import os
import sys
import time
from datetime import timedelta
from sqlalchemy import inspect

# Ensure project root is on path when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, g, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config.settings import DevelopmentConfig
from api.routes.predict import predict_bp
from api.routes.auth import auth_bp
from api.routes.mfa import mfa_bp
from api.routes.docs import docs_bp
from api.routes.health import health_bp
from api.extensions import limiter
from app.models import db, RefreshToken
from api.metrics import metrics_bp, record_request_metrics
import logging


def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    def _to_timedelta(value, default_seconds: int) -> timedelta:
        if isinstance(value, timedelta):
            return value
        seconds = value if value is not None else default_seconds
        return timedelta(seconds=seconds)

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = _to_timedelta(
        app.config.get("JWT_ACCESS_TOKEN_EXPIRES"), 900
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = _to_timedelta(
        app.config.get("JWT_REFRESH_TOKEN_EXPIRES"), 2592000
    )

    # JWT cookie settings
    is_prod = not app.debug and not app.testing
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_REFRESH_COOKIE_NAME"] = "refresh_token"
    app.config["JWT_REFRESH_COOKIE_PATH"] = "/api/auth/refresh"
    app.config["JWT_COOKIE_SAMESITE"] = "Strict" if is_prod else "Lax"
    app.config["JWT_COOKIE_SECURE"] = True if is_prod else False
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-Token"
    app.config["JWT_REFRESH_CSRF_HEADER_NAME"] = "X-CSRF-Token"

    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    limiter.init_app(app)
    
    @jwt.unauthorized_loader
    def handle_missing_or_bad_token(reason):
        reason_lower = reason.lower()
        if "csrf" in reason_lower:
            return {"msg": "Missing or invalid CSRF token", "error": "csrf_failed"}, 403
        return {"msg": reason, "error": "unauthorized"}, 401

    # Enable CORS with credentials
    CORS(app, origins=app.config.get("CORS_ORIGINS"), supports_credentials=True)

    # Register blueprints
    app.register_blueprint(predict_bp, url_prefix="/api")
    app.register_blueprint(auth_bp)
    app.register_blueprint(mfa_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)

    # Token Blocklist Callback
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        token = db.session.query(RefreshToken).filter_by(jti=jti).scalar()
        return token is not None and token.revoked

    # Optionally ensure refresh_token table exists (avoid blocking startup if DB is down)
    if app.config.get("AUTO_CREATE_REFRESH_TOKEN_TABLE", False):
        with app.app_context():
            try:
                inspector = inspect(db.engine)
                if inspector.has_table("app_user") and not inspector.has_table(
                    "refresh_token"
                ):
                    db.metadata.create_all(
                        bind=db.engine, tables=[RefreshToken.__table__]
                    )
            except Exception:
                app.logger.warning(
                    "Startup DB check failed; skipping refresh_token auto-create",
                    exc_info=True,
                )

    # Configure logging
    if not app.debug:
        logging.basicConfig(
            level=app.config.get("LOG_LEVEL", "INFO"),
            format=app.config.get(
                "LOG_FORMAT",
                "%(asctime)s %(levelname)s %(name)s %(message)s",
            ),
        )

    @app.before_request
    def _start_timer():
        g._start_time = time.monotonic()

    @app.after_request
    def _log_and_metrics(response):
        start = getattr(g, "_start_time", None)
        if start is not None:
            duration_ms = (time.monotonic() - start) * 1000.0
            if app.config.get("METRICS_ENABLED", True):
                record_request_metrics(duration_ms, response.status_code)
            if app.config.get("LOG_REQUESTS", False):
                if request.path not in app.config.get("LOG_EXCLUDE_PATHS", set()):
                    app.logger.info(
                        "request method=%s path=%s status=%s duration_ms=%.2f ip=%s",
                        request.method,
                        request.path,
                        response.status_code,
                        duration_ms,
                        request.remote_addr,
                    )
        return response

    # Ensure sessions are cleaned up per request/appcontext
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        try:
            db.session.remove()
        except Exception:
            pass

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
