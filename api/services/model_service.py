import pandas as pd
from core.models.predictor import load_model, predict_proba


def predict_all_probabilities(data: dict) -> dict:
    feature_names = [
        "age",
        "sex",
        "conners_inattention_score",
        "conners_hyperactivity",
        "cbcl_attention_score",
        "sleep_problems",
    ]

    # DataFrame con una sola fila
    X = pd.DataFrame([data], columns=feature_names)

    predictions = {}

    # TDAH
    adhd_model = load_model("adhd")
    predictions["adhd"] = round(predict_proba(adhd_model, X), 2)

    return predictions

