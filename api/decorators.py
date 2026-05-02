from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models import AppUser, db
from api.security import requires_mfa_enrollment


def _error(message: str, code: str, status: int):
    return jsonify({"msg": message, "error": code}), status

def roles_required(*required_roles):
    """
    Decorator to protect endpoints requiring specific roles.
    Checks if the JWT has any of the required roles.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("mfa_enrollment"):
                return _error("Enrollment token not allowed", "mfa_enrollment_only", 403)

            user_roles = {str(role).upper() for role in (claims.get("roles", []) or [])}
            required = {str(role).upper() for role in required_roles}

            if user_roles & required:
                return fn(*args, **kwargs)
            return _error("Insufficient permissions", "insufficient_permissions", 403)
        return decorator
    return wrapper


def enforce_mfa():
    """
    Decorator to block access if the user's roles require MFA but it is not enabled.
    Intended for sensitive endpoints; skips enforcement for endpoints that explicitly handle MFA.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            identity = get_jwt_identity()
            user = db.session.get(AppUser, identity) if identity else None
            if not user:
                return jsonify(msg="Invalid user"), 401
            if requires_mfa_enrollment(user) and not user.mfa_enabled:
                return jsonify(msg="MFA enrollment required"), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper
