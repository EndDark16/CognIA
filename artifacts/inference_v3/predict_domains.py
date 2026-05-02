from pathlib import Path
import joblib

def load_model(model_path: str):
    return joblib.load(Path(model_path))

def predict_domains(model, X):
    prob = model.predict_proba(X)[:, 1]
    return prob
