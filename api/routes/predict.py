# api/routes/predict.py
from flask import Blueprint, request, jsonify
from api.schemas.predict_schema import PredictSchema
from api.services.model_service import predict_all_probabilities

predict_bp = Blueprint("predict", __name__)

@predict_bp.route("/predict", methods=["POST"])
def predict():
    schema = PredictSchema()
    errors = schema.validate(request.json)
    if errors:
        return jsonify({"errors": errors}), 400

    data = request.json
    predictions = predict_all_probabilities(data)
    return jsonify({"predictions": predictions})
