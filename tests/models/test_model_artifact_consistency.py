import json
import os
import sys
from pathlib import Path

# Garantiza que la raiz del proyecto este en el sys.path al ejecutar pytest
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.services import model_service


def _valid_predict_payload():
    return {
        "age": 10,
        "sex": 1,
        "conners_inattention_score": 12.5,
        "conners_hyperactivity": 8.1,
        "cbcl_attention_score": 14.0,
        "sleep_problems": 0,
    }


def test_runtime_manifest_points_to_existing_model():
    manifest_path = Path("reports") / "deploy_finalization" / "final_runtime_model_manifest.csv"
    assert manifest_path.exists()

    lines = [line.strip() for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 2, "El manifest de runtime no tiene filas de datos"

    header = lines[0].strip('"').split(",")
    values = lines[1].strip('"').split(",")
    runtime_row = dict(zip(header, values))

    model_path = Path(runtime_row["path"])
    assert model_path.exists(), f"No existe el binario declarado en runtime manifest: {model_path}"
    assert runtime_row["runtime_required"] == "yes"
    assert runtime_row["keep_in_repo"] == "yes"


def test_runtime_expected_model_name_matches_predictor_convention():
    expected = Path("models") / "adhd_model.pkl"
    assert expected.exists()


def test_inference_v4_scope_matches_final_scope_docs():
    scope_json_path = Path("artifacts") / "inference_v4" / "promotion_scope.json"
    final_scope_doc = Path("reports") / "final_closure" / "inference_scope_final.md"
    assert scope_json_path.exists()
    assert final_scope_doc.exists()

    data = json.loads(scope_json_path.read_text(encoding="utf-8"))
    assert data["active_domains"] == ["adhd", "anxiety", "conduct", "depression"]
    assert data["hold_domains"] == ["elimination"]


def test_runtime_predictions_do_not_activate_hold_domain():
    scope = json.loads((Path("artifacts") / "inference_v4" / "promotion_scope.json").read_text(encoding="utf-8"))
    hold_domains = set(scope["hold_domains"])
    result = model_service.predict_all_probabilities(_valid_predict_payload())
    assert set(result.keys()).isdisjoint(hold_domains)
