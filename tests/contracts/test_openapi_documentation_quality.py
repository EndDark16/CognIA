import os
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


HTTP_METHODS = ("get", "post", "put", "patch", "delete")
REQUIRED_DESCRIPTION_MARKERS = (
    "**Objetivo funcional real:**",
    "**Recurso/proceso que gestiona:**",
    "**Cuando debe usarse:**",
    "**Actor o rol que suele consumirlo:**",
    "**Seguridad aplicable:**",
    "**Parametros de entrada:**",
    "**Body de solicitud:**",
    "**Comportamiento esperado del endpoint:**",
    "**Respuesta exitosa y significado funcional:**",
    "**Errores posibles documentados:**",
    "**Persistencia / workflow / trazabilidad:**",
    "**Clasificacion del endpoint:**",
)


def _load_openapi():
    path = Path(PROJECT_ROOT) / "docs" / "openapi.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_openapi_operations_have_professional_spanish_documentation():
    spec = _load_openapi()

    operation_ids = []
    missing = []
    mechanical_summaries = []
    missing_markers = []

    for path, item in (spec.get("paths") or {}).items():
        for method in HTTP_METHODS:
            op = (item or {}).get(method)
            if not op:
                continue

            summary = str(op.get("summary") or "").strip()
            description = str(op.get("description") or "").strip()
            operation_id = str(op.get("operationId") or "").strip()

            if not summary or not description or not operation_id:
                missing.append((method.upper(), path))
                continue

            if summary.upper().startswith(("GET ", "POST ", "PATCH ", "DELETE ", "PUT ")):
                mechanical_summaries.append((method.upper(), path, summary))

            for marker in REQUIRED_DESCRIPTION_MARKERS:
                if marker not in description:
                    missing_markers.append((method.upper(), path, marker))
                    break

            operation_ids.append(operation_id)

    assert not missing, f"Operations with missing summary/description/operationId: {missing}"
    assert not mechanical_summaries, f"Mechanical summaries detected: {mechanical_summaries}"
    assert not missing_markers, f"Descriptions missing required sections: {missing_markers}"
    assert len(operation_ids) == len(
        set(operation_ids)
    ), "OpenAPI operationId values must be unique"


def test_openapi_info_description_preserves_scope_and_clinical_caveat():
    spec = _load_openapi()
    text = str(((spec.get("info") or {}).get("description")) or "").lower()

    assert "screening" in text or "tamiz" in text
    assert "no constituye diagnostico" in text or "no diagnostico" in text
    assert "docs/openapi.yaml" in text
