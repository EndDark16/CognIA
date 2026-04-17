# api/routes/predict.py
from flask import Blueprint, current_app, jsonify, request
from marshmallow import ValidationError

from api.extensions import limiter
from api.schemas.predict_schema import PredictSchema
from api.services.model_service import predict_all_probabilities

predict_bp = Blueprint("predict", __name__)


def _error(message: str, error: str, status_code: int, details=None):
    payload = {"msg": message, "error": error}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


@predict_bp.route("/predict", methods=["POST"])
@limiter.limit(lambda: current_app.config.get("PREDICT_RATE_LIMIT", "30 per minute"))
def predict():
    payload = request.get_json(silent=True)
    if payload is None:
        return _error(
            "Validation error",
            "validation_error",
            400,
            {"body": ["JSON body is required"]},
        )

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

    return jsonify({"predictions": predictions}), 200
