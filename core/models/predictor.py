import joblib
import os
import numpy as np
import pandas as pd
from functools import lru_cache


@lru_cache(maxsize=16)
def load_model(model_name: str):
    model_path = os.path.join("models", f"{model_name}_model.pkl")
    return joblib.load(model_path)

def predict_proba(model, features) -> float:
    # Asegurar que la entrada sea 2D
    if isinstance(features, dict):
        features = pd.DataFrame([features])
    elif isinstance(features, list) or isinstance(features, np.ndarray):
        features = np.array(features).reshape(1, -1)
    
    return model.predict_proba(features)[0][1]  # probabilidad clase 1
