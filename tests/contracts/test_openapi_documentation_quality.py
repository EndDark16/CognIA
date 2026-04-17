import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
REQUIRED_SECTIONS = {
    "**Objetivo funcional**",
    "**Cuando debe usarse**",
    "**Actor que lo consume**",
    "**Seguridad aplicable**",
    "**Entrada esperada**",
    "**Resultado exitoso**",
    "**Errores posibles y causa funcional**",
    "**Estado contractual**",
}
VALID_CONTRACT_STATUS = {
    "KEEP_ACTIVE",
    "KEEP_ACTIVE_BUT_LEGACY",
    "INTERNAL_ONLY",
    "DEPRECATE_PUBLIC",
    "REMOVE_AFTER_COMPAT_WINDOW",
    "DUPLICATE_TO_CONSOLIDATE",
}


def _iter_operations(spec: dict):
    for path, item in (spec.get("paths") or {}).items():
        for method, operation in item.items():
            if method in HTTP_METHODS and isinstance(operation, dict):
                yield path, method, operation


def test_openapi_documentation_quality_contract():
    openapi_path = Path(PROJECT_ROOT) / "docs" / "openapi.yaml"
    raw = openapi_path.read_text(encoding="utf-8")
    spec = yaml.safe_load(raw)

    operations = list(_iter_operations(spec))
    assert operations, "OpenAPI no contiene operaciones."

    missing_sections = []
    generic_success = []
    missing_status = []

    for path, method, operation in operations:
        summary = str(operation.get("summary") or "").strip()
        description = str(operation.get("description") or "").strip()
        contract_status = operation.get("x-contract-status")

        assert summary, f"summary vacio en {method.upper()} {path}"
        assert description, f"description vacia en {method.upper()} {path}"

        for section in REQUIRED_SECTIONS:
            if section not in description:
                missing_sections.append((path, method, section))

        if contract_status not in VALID_CONTRACT_STATUS:
            missing_status.append((path, method, contract_status))

        for code, response in (operation.get("responses") or {}).items():
            if not isinstance(response, dict):
                continue
            desc = str(response.get("description") or "").strip().lower()
            if desc in {"success", "ok"}:
                generic_success.append((path, method, code))

    assert not missing_sections, f"Secciones obligatorias ausentes en descripciones: {missing_sections}"
    assert not generic_success, f"Respuestas con descripcion generica detectadas: {generic_success}"
    assert not missing_status, f"Estado contractual invalido o ausente: {missing_status}"
    assert "\\n\\n" not in raw, "Se detectaron literales \\n\\n en openapi.yaml"


def test_endpoint_lifecycle_matrix_exists_and_has_rows():
    matrix_path = Path(PROJECT_ROOT) / "docs" / "endpoint_lifecycle_matrix.md"
    assert matrix_path.exists(), "Falta docs/endpoint_lifecycle_matrix.md"
    text = matrix_path.read_text(encoding="utf-8")
    assert "| Endpoint actual | Modulo/version | Endpoint que lo reemplaza |" in text
    row_count = sum(1 for line in text.splitlines() if line.startswith("| `"))
    assert row_count >= 100, f"La matriz parece incompleta (filas={row_count})"

