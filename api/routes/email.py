from flask import Blueprint, jsonify, request, current_app
from marshmallow import ValidationError
from itsdangerous import BadSignature, SignatureExpired

from api.extensions import limiter
from api.schemas.email_schema import EmailUnsubscribeSchema
from api.services.unsubscribe_service import verify_unsubscribe_token, upsert_unsubscribe


email_bp = Blueprint("email", __name__, url_prefix="/api/email")


def _collect_unsubscribe_payload() -> dict:
    payload = {}
    if request.args:
        payload.update(request.args.to_dict(flat=True))
    if request.is_json:
        body = request.get_json(silent=True) or {}
        for key, value in body.items():
            payload.setdefault(key, value)
    if request.form:
        for key in request.form:
            payload.setdefault(key, request.form.get(key))
    return payload


@email_bp.route("/unsubscribe", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("EMAIL_UNSUBSCRIBE_RATE_LIMIT", "10 per 10 minutes"))
def email_unsubscribe():
    schema = EmailUnsubscribeSchema()
    try:
        data = schema.load(_collect_unsubscribe_payload())
    except ValidationError as err:
        return jsonify(
            {"msg": "Validation error", "error": "validation_error", "details": err.messages}
        ), 400

    token = data["token"]
    reason = data.get("reason")

    try:
        email = verify_unsubscribe_token(token)
    except (BadSignature, SignatureExpired):
        return jsonify({"msg": "Invalid or expired token", "error": "invalid_token"}), 400
    except Exception:
        current_app.logger.exception("Failed to verify unsubscribe token")
        return jsonify({"msg": "Invalid or expired token", "error": "invalid_token"}), 400

    forwarded_for = request.headers.get("X-Forwarded-For")
    request_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr

    try:
        upsert_unsubscribe(
            email=email,
            reason=reason,
            source="unsubscribe_link",
            request_ip=request_ip,
            user_agent=request.headers.get("User-Agent"),
        )
    except Exception:
        current_app.logger.exception("Failed to persist unsubscribe request")
        return jsonify({"msg": "Unable to process request", "error": "server_error"}), 500

    return jsonify({"message": "Unsubscribed"}), 200
