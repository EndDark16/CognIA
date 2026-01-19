from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.models import AppUser, db
from api.security import requires_mfa_enrollment

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
            user_roles = claims.get("roles", [])
            
            # Check intersection of user roles and required roles
            if not set(required_roles).isdisjoint(user_roles):
                return fn(*args, **kwargs)
            else:
                return jsonify(msg="Insufficient permissions"), 403
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
