# api/routes/predict.py
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from api.extensions import limiter
from api.schemas.predict_schema import PredictSchema
from api.services.model_service import predict_all_probabilities
from api.services import transport_crypto_service as transport_crypto

predict_bp = Blueprint("predict", __name__)


def _error(message: str, error: str, status_code: int, details=None):
    payload = {"msg": message, "error": error}
    if details is not None:
        payload["details"] = details
        payload["errors"] = details
    return jsonify(payload), status_code


def _decode_sensitive_payload() -> tuple[dict, transport_crypto.TransportContext]:
    payload = request.get_json(silent=True) or {}
    return transport_crypto.decode_sensitive_request_payload(payload)


def _sensitive_response(payload: dict, status_code: int, context: transport_crypto.TransportContext):
    encoded_payload, headers = transport_crypto.encode_sensitive_response_payload(payload, context)
    response = jsonify(encoded_payload)
    response.status_code = status_code
    response.headers["Cache-Control"] = "no-store"
    for key, value in headers.items():
        response.headers[key] = value
    return response


@predict_bp.route("/predict", methods=["POST"])
@jwt_required()
@limiter.limit(lambda: current_app.config.get("PREDICT_RATE_LIMIT", "30 per minute"))
def predict():
    try:
        payload, transport_context = _decode_sensitive_payload()
    except transport_crypto.TransportCryptoError as exc:
        return _error(exc.message, exc.code, exc.status_code)

    schema = PredictSchema()
    try:
        data = schema.load(payload)
    except ValidationError as exc:
        return _error("Validation error", "validation_error", 400, exc.messages)

    try:
        predictions = predict_all_probabilities(data)
    except Exception:
        current_app.logger.error("predict_error", exc_info=True)
        return _error("Internal server error", "server_error", 500)

    return _sensitive_response({"predictions": predictions}, 200, transport_context)
