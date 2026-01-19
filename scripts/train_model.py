import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib

# load dataset
df = pd.read_csv("../data/adhd_dataset_simulated.csv")

# Variables independientes (X) y dependiente (y)
X = df.drop("adhd_dx", axis=1)
y = df["adhd_dx"]

# Dividir en entrenamiento y prueba
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# Crear y entrenar modelo Random Forest
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluación
y_pred = model.predict(X_test)
print("Classification Report:\n")
print(classification_report(y_test, y_pred))

# Guardar modelo entrenado
joblib.dump(model, "../models/adhd_model.pkl")
print("\nModelo guardado como 'adhd_model.pkl'")
