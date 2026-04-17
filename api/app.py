# api/app.py

import os
import sys
import time
import importlib
from datetime import timedelta, datetime, timezone
from sqlalchemy import inspect

# Ensure project root is on path when running this file directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, g, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config.settings import DevelopmentConfig
from api.routes.predict import predict_bp
from api.routes.auth import auth_bp
from api.routes.mfa import mfa_bp
from api.routes.docs import docs_bp
from api.routes.health import health_bp
from api.routes.email import email_bp
from api.routes.admin import admin_bp
from api.routes.questionnaires import questionnaires_bp
from api.routes.evaluations import evaluations_bp
from api.routes.users import users_bp
from api.routes.problem_reports import problem_reports_bp
from api.extensions import limiter
from app.models import db, RefreshToken, AppUser
from api.metrics import metrics_bp, record_request_metrics
import logging
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DBAPIError
from flask_limiter.errors import RateLimitExceeded
from marshmallow import ValidationError
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app(config_class=DevelopmentConfig):
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config.from_object(config_class)
    if app.config.get("TRUST_PROXY_HEADERS", False):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=int(app.config.get("PROXY_FIX_X_FOR", 1)),
            x_proto=int(app.config.get("PROXY_FIX_X_PROTO", 1)),
            x_host=int(app.config.get("PROXY_FIX_X_HOST", 1)),
            x_port=int(app.config.get("PROXY_FIX_X_PORT", 1)),
            x_prefix=int(app.config.get("PROXY_FIX_X_PREFIX", 1)),
        )

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
    cross_site_cookies = bool(app.config.get("AUTH_CROSS_SITE_COOKIES", False))
    cookie_secure_cfg = app.config.get("JWT_COOKIE_SECURE")
    cookie_samesite_cfg = app.config.get("JWT_COOKIE_SAMESITE")
    cookie_secure = is_prod if cookie_secure_cfg is None else bool(cookie_secure_cfg)

    if cookie_samesite_cfg:
        samesite = str(cookie_samesite_cfg).strip().capitalize()
        if samesite not in {"Lax", "Strict", "None"}:
            samesite = "Strict" if is_prod else "Lax"
    else:
        if cross_site_cookies and is_prod:
            samesite = "None"
        else:
            samesite = "Strict" if is_prod else "Lax"

    if samesite == "None":
        # Browsers reject SameSite=None cookies unless Secure=true.
        cookie_secure = True

    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_REFRESH_COOKIE_NAME"] = "refresh_token"
    app.config["JWT_REFRESH_COOKIE_PATH"] = "/api/auth/refresh"
    app.config["JWT_COOKIE_SAMESITE"] = samesite
    app.config["JWT_COOKIE_SECURE"] = cookie_secure
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-Token"
    app.config["JWT_REFRESH_CSRF_HEADER_NAME"] = "X-CSRF-Token"
    cookie_domain = app.config.get("JWT_COOKIE_DOMAIN")
    if cookie_domain:
        app.config["JWT_COOKIE_DOMAIN"] = cookie_domain

    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    limiter.init_app(app)
    
    @jwt.unauthorized_loader
    def handle_missing_or_bad_token(reason):
        reason_lower = reason.lower()
        if "csrf" in reason_lower:
            return {"msg": "Missing or invalid CSRF token", "error": "csrf_failed"}, 403
        return {"msg": "Unauthorized", "error": "unauthorized"}, 401

    @jwt.invalid_token_loader
    def handle_invalid_token(reason):
        return {"msg": "Unauthorized", "error": "unauthorized"}, 401

    @jwt.expired_token_loader
    def handle_expired_token(jwt_header, jwt_payload):
        return {"msg": "Token expired", "error": "token_expired"}, 401

    @jwt.revoked_token_loader
    def handle_revoked_token(jwt_header, jwt_payload):
        return {"msg": "Token revoked", "error": "token_revoked"}, 401

    # Enable CORS with credentials
    CORS(
        app,
        origins=app.config.get("CORS_ORIGINS"),
        supports_credentials=True,
        always_send=False,
        vary_header=True,
    )

    def _json_error(message: str, error_code: str, status_code: int, details=None):
        payload = {"msg": message, "error": error_code}
        if details is not None:
            payload["details"] = details
        return jsonify(payload), status_code
    
    def _safe_rollback():
        try:
            db.session.rollback()
        except Exception:
            pass

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(exc):
        return _json_error("Too many requests", "rate_limited", 429)

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc):
        return _json_error("Validation error", "validation_error", 400, exc.messages)

    @app.errorhandler(OperationalError)
    @app.errorhandler(DBAPIError)
    def handle_db_unavailable(exc):
        _safe_rollback()
        app.logger.error("Database connection error: %s", exc, exc_info=True)
        return _json_error("Service unavailable", "db_unavailable", 503)

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(exc):
        _safe_rollback()
        app.logger.error("Database error: %s", exc, exc_info=True)
        return _json_error("Database error", "db_error", 500)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        code = exc.code or 500
        name = (exc.name or "http_error").lower().replace(" ", "_")
        return _json_error(exc.description, name, code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        app.logger.error("Unhandled error: %s", exc, exc_info=True)
        return _json_error("Internal server error", "server_error", 500)

    # Register blueprints
    app.register_blueprint(predict_bp, url_prefix="/api")
    app.register_blueprint(auth_bp)
    app.register_blueprint(mfa_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(questionnaires_bp)
    app.register_blueprint(evaluations_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(admin_bp)
    def _normalize_required_optional_blueprints(value) -> set[str]:
        if value is None:
            return set()
        if isinstance(value, str):
            return {item.strip() for item in value.split(",") if item.strip()}
        if isinstance(value, (list, tuple, set)):
            return {str(item).strip() for item in value if str(item).strip()}
        return set()

    def _register_optional_blueprint(module_path: str, blueprint_name: str, blueprint_key: str) -> None:
        strict = bool(app.config.get("OPTIONAL_BLUEPRINTS_STRICT", True))
        required = _normalize_required_optional_blueprints(
            app.config.get("OPTIONAL_BLUEPRINTS_REQUIRED", [])
        )
        is_required = blueprint_key in required
        try:
            module = importlib.import_module(module_path)
            blueprint = getattr(module, blueprint_name)
        except Exception as exc:
            app.logger.exception(
                "Optional blueprint import failed: %s (%s)", blueprint_key, module_path
            )
            if strict and is_required:
                raise RuntimeError(
                    f"Required blueprint '{blueprint_key}' failed to import"
                ) from exc
            return
        app.register_blueprint(blueprint)

    _register_optional_blueprint(
        "api.routes.questionnaire_runtime",
        "questionnaire_runtime_bp",
        "questionnaire_runtime",
    )
    _register_optional_blueprint(
        "api.routes.questionnaire_v2",
        "questionnaire_v2_bp",
        "questionnaire_v2",
    )
    app.register_blueprint(problem_reports_bp)

    # Token Blocklist Callback
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        token = db.session.query(RefreshToken).filter_by(jti=jti).scalar()
        if token is not None and token.revoked:
            return True

        try:
            identity = jwt_payload.get("sub")
            user = db.session.get(AppUser, identity)
            if user and user.password_changed_at:
                iat = jwt_payload.get("iat")
                if iat:
                    issued_at = datetime.fromtimestamp(iat, timezone.utc)
                    pwd_changed = user.password_changed_at
                    if pwd_changed.tzinfo is None:
                        pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
                    if issued_at <= pwd_changed:
                        return True
            if user and user.sessions_revoked_at:
                iat = jwt_payload.get("iat")
                if iat:
                    issued_at = datetime.fromtimestamp(iat, timezone.utc)
                    revoked_at = user.sessions_revoked_at
                    if revoked_at.tzinfo is None:
                        revoked_at = revoked_at.replace(tzinfo=timezone.utc)
                    if issued_at <= revoked_at:
                        return True
        except Exception:
            return False
        return False

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

        if app.config.get("SECURITY_HEADERS_ENABLED", True):
            response.headers.setdefault(
                "X-Content-Type-Options",
                app.config.get("SECURITY_CONTENT_TYPE_OPTIONS", "nosniff"),
            )
            response.headers.setdefault(
                "X-Frame-Options",
                app.config.get("SECURITY_FRAME_OPTIONS", "DENY"),
            )
            response.headers.setdefault(
                "Referrer-Policy",
                app.config.get("SECURITY_REFERRER_POLICY", "strict-origin-when-cross-origin"),
            )
            csp = app.config.get("SECURITY_CSP")
            if csp:
                response.headers.setdefault("Content-Security-Policy", csp)
            permissions_policy = app.config.get("SECURITY_PERMISSIONS_POLICY")
            if permissions_policy:
                response.headers.setdefault("Permissions-Policy", permissions_policy)

            forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
            is_secure_request = request.is_secure or forwarded_proto.split(",")[0].strip().lower() == "https"
            hsts_seconds = int(app.config.get("SECURITY_HSTS_SECONDS", 0))
            if is_secure_request and hsts_seconds > 0:
                hsts_value = f"max-age={hsts_seconds}"
                if app.config.get("SECURITY_HSTS_INCLUDE_SUBDOMAINS", True):
                    hsts_value += "; includeSubDomains"
                if app.config.get("SECURITY_HSTS_PRELOAD", False):
                    hsts_value += "; preload"
                response.headers.setdefault("Strict-Transport-Security", hsts_value)
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
