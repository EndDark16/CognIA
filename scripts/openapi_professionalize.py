import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def to_openapi_path(path: str) -> str:
    normalized = path
    normalized = normalized.replace("<string:", "<")
    normalized = normalized.replace("<int:", "<")
    normalized = normalized.replace("<uuid:", "<")
    while "<" in normalized and ">" in normalized:
        start = normalized.index("<")
        end = normalized.index(">", start)
        name = normalized[start + 1 : end].split(":")[-1]
        normalized = normalized[:start] + "{" + name + "}" + normalized[end + 1 :]
    return normalized


def canonical(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def infer_tag(path: str) -> str:
    if path in {"/healthz", "/readyz", "/metrics"}:
        return "Health"
    if path in {"/docs", "/openapi.yaml"}:
        return "Docs"
    if path.startswith("/api/auth"):
        return "Auth"
    if path.startswith("/api/mfa"):
        return "MFA"
    if path.startswith("/api/email"):
        return "Email"
    if path.startswith("/api/problem-reports") or path.startswith("/api/admin/problem-reports"):
        return "ProblemReports"
    if path.startswith("/api/admin"):
        return "Admin"
    if path.startswith("/api/v1/users"):
        return "Users"
    if path.startswith("/api/v1/evaluations"):
        return "Evaluations"
    if path.startswith("/api/v1/questionnaire-runtime/admin"):
        return "QuestionnaireRuntimeAdmin"
    if path.startswith("/api/v1/questionnaire-runtime"):
        return "QuestionnaireRuntime"
    if path.startswith("/api/v2/dashboard"):
        return "Dashboard"
    if path.startswith("/api/v2/reports"):
        return "Reports"
    if path.startswith("/api/v2/questionnaires"):
        return "QuestionnaireV2"
    if path.startswith("/api/v1/questionnaires"):
        return "Questionnaires"
    if path.startswith("/api/predict"):
        return "Predict"
    return "Misc"


def infer_module(path: str) -> str:
    if path.startswith("/api/v2/questionnaires"):
        return "questionnaire_v2"
    if path.startswith("/api/v2/dashboard"):
        return "dashboard_v2"
    if path.startswith("/api/v2/reports"):
        return "reports_v2"
    if path.startswith("/api/v1/questionnaire-runtime"):
        return "questionnaire_runtime_v1"
    if path.startswith("/api/v1/questionnaires"):
        return "questionnaires_v1"
    if path.startswith("/api/v1/users"):
        return "users_v1"
    if path.startswith("/api/admin/users"):
        return "admin_users"
    if path.startswith("/api/admin"):
        return "admin"
    if path.startswith("/api/problem-reports") or path.startswith("/api/admin/problem-reports"):
        return "problem_reports"
    if path.startswith("/api/auth"):
        return "auth"
    if path.startswith("/api/mfa"):
        return "mfa"
    if path.startswith("/api/email"):
        return "email"
    if path.startswith("/api/predict"):
        return "predict_legacy"
    if path in {"/healthz", "/readyz", "/metrics"}:
        return "health"
    if path in {"/docs", "/openapi.yaml"}:
        return "docs"
    return "misc"


def classify_contract(path: str) -> dict:
    replaced_by = None
    reason = ""
    status = "KEEP_ACTIVE"

    if path == "/api/predict":
        status = "DEPRECATE_PUBLIC"
        reason = "Ruta experimental heredada sin contrato estable de producto."
    elif path.startswith("/api/v1/questionnaires"):
        status = "KEEP_ACTIVE_BUT_LEGACY"
        reason = "Convive por compatibilidad con clientes v1; la ruta operativa principal es v2."
        if path == "/api/v1/questionnaires/active":
            replaced_by = "/api/v2/questionnaires/active"
        elif path == "/api/v1/questionnaires/active/clone":
            replaced_by = "/api/admin/questionnaires/{template_id}/clone"
        elif path == "/api/v1/questionnaires/{template_id}/activate":
            replaced_by = "/api/admin/questionnaires/{template_id}/publish"
    elif path.startswith("/api/v1/questionnaire-runtime"):
        status = "KEEP_ACTIVE_BUT_LEGACY"
        reason = "Flujo runtime v1 mantenido por compatibilidad mientras se migra a cuestionarios v2."
        if "questionnaire/active" in path:
            replaced_by = "/api/v2/questionnaires/active"
    elif path.startswith("/api/v1/users"):
        status = "KEEP_ACTIVE_BUT_LEGACY"
        replaced_by = "/api/admin/users"
        reason = "Gestion de usuarios v1 mantenida por clientes legacy; administracion principal en /api/admin/users."
    elif path.startswith("/api/v2"):
        status = "KEEP_ACTIVE"
        reason = "Contrato operativo actual para sesiones, historia, reportes y dashboards."
    elif path.startswith("/api/admin"):
        status = "KEEP_ACTIVE"
        reason = "Contrato administrativo vigente para backoffice y operaciones de seguridad."
    elif path.startswith("/api/problem-reports") or path.startswith("/api/admin/problem-reports"):
        status = "KEEP_ACTIVE"
        reason = "Contrato vigente para trazabilidad operativa de incidentes y soporte."
    elif path in {"/docs", "/openapi.yaml"}:
        status = "KEEP_ACTIVE"
        reason = "Endpoint documental y de descubrimiento de contrato."
    elif path in {"/healthz", "/readyz", "/metrics"}:
        status = "KEEP_ACTIVE"
        reason = "Endpoint operativo de observabilidad y estado del servicio."
    elif path.startswith("/api/auth") or path.startswith("/api/mfa") or path.startswith("/api/email"):
        status = "KEEP_ACTIVE"
        reason = "Contrato de autenticacion, seguridad y soporte vigente."

    if not reason:
        reason = "Contrato vigente sin reemplazo directo en esta version."

    action = {
        "KEEP_ACTIVE": "mantener visible",
        "KEEP_ACTIVE_BUT_LEGACY": "mantener visible y marcar deprecated",
        "INTERNAL_ONLY": "documentar como internal",
        "DEPRECATE_PUBLIC": "marcar deprecated",
        "REMOVE_AFTER_COMPAT_WINDOW": "retirar del contrato publico",
        "DUPLICATE_TO_CONSOLIDATE": "mantener visible con nota de consolidacion",
    }.get(status, "mantener visible")

    compat_risk = {
        "KEEP_ACTIVE": "bajo",
        "KEEP_ACTIVE_BUT_LEGACY": "medio",
        "INTERNAL_ONLY": "bajo",
        "DEPRECATE_PUBLIC": "alto",
        "REMOVE_AFTER_COMPAT_WINDOW": "alto",
        "DUPLICATE_TO_CONSOLIDATE": "medio",
    }.get(status, "medio")

    return {
        "status": status,
        "replaced_by": replaced_by,
        "reason": reason,
        "openapi_action": action,
        "compat_risk": compat_risk,
    }


def security_requirements(path: str) -> tuple[list, list[str]]:
    roles = []
    if path in {"/healthz", "/readyz", "/docs", "/openapi.yaml"}:
        return [], roles
    if path == "/metrics":
        return [{"metricsToken": []}, {}], roles
    if path in {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/login/mfa",
        "/api/auth/password/forgot",
        "/api/auth/password/reset",
        "/api/auth/password/reset/verify",
        "/api/email/unsubscribe",
        "/api/predict",
    }:
        return [], roles
    if path == "/api/auth/refresh":
        return [{"cookieAuth": [], "csrfHeader": []}], roles
    if path.startswith("/api/admin") or path.startswith("/api/v1/users"):
        roles = ["ADMIN"]
        return [{"bearerAuth": []}], roles
    if path.startswith("/api/v1/questionnaire-runtime/admin"):
        roles = ["ADMIN"]
        return [{"bearerAuth": []}], roles
    return [{"bearerAuth": []}], roles


def action_verb(method: str, path: str) -> str:
    method = method.lower()
    if method == "get":
        return "Consultar"
    if method == "delete":
        return "Eliminar"
    if method == "patch":
        return "Actualizar"
    if method == "put":
        return "Reemplazar"
    if method == "post":
        if any(k in path for k in ["submit", "publish", "approve", "reject", "refresh", "login", "logout"]):
            return "Ejecutar"
        if "clone" in path:
            return "Clonar"
        if "activate" in path or "active" in path:
            return "Activar"
        return "Crear"
    return "Operar"


def collect_parameters(path_item: dict, op: dict, location: str) -> list[str]:
    merged = []
    for source in (path_item.get("parameters", []) or [], op.get("parameters", []) or []):
        for p in source:
            if isinstance(p, dict) and p.get("in") == location:
                if "$ref" in p:
                    merged.append(f"{p['$ref'].split('/')[-1]} (referencia)")
                else:
                    name = p.get("name", "param")
                    required = "obligatorio" if p.get("required") else "opcional"
                    merged.append(f"{name} ({required})")
    return list(dict.fromkeys(merged))


def ensure_path_parameters(path: str, path_item: dict):
    placeholders = re.findall(r"\{([^}]+)\}", path)
    if not placeholders:
        return
    params = path_item.setdefault("parameters", [])
    existing = {p.get("name"): p for p in params if isinstance(p, dict) and p.get("in") == "path"}

    if len(placeholders) == 1 and "id" in existing and placeholders[0] != "id":
        existing["id"]["name"] = placeholders[0]
        existing["id"]["description"] = f"Identificador del recurso `{placeholders[0]}` en la ruta."
        existing[placeholders[0]] = existing["id"]
        del existing["id"]

    for name in placeholders:
        if name not in existing:
            params.append(
                {
                    "name": name,
                    "in": "path",
                    "required": True,
                    "description": f"Identificador del recurso `{name}` en la ruta.",
                    "schema": {"type": "string"},
                }
            )
        else:
            existing[name]["required"] = True
            existing[name]["schema"] = existing[name].get("schema") or {"type": "string"}
            existing[name]["description"] = existing[name].get("description") or f"Identificador del recurso `{name}` en la ruta."


def success_description(code: str) -> str:
    mapping = {
        "200": "Operacion completada correctamente y la respuesta incluye el resultado solicitado.",
        "201": "Recurso creado correctamente o accion iniciada con exito.",
        "202": "Solicitud aceptada para procesamiento posterior.",
        "204": "Operacion completada sin contenido de respuesta.",
    }
    return mapping.get(str(code), "Respuesta de exito de la operacion solicitada.")


def error_description(code: str) -> str:
    mapping = {
        "400": "Solicitud invalida por formato, validacion o reglas de negocio.",
        "401": "No autenticado o token invalido/expirado.",
        "403": "Autenticado sin permisos suficientes para esta operacion.",
        "404": "Recurso no encontrado o no visible para el actor autenticado.",
        "409": "Conflicto de estado o de unicidad al ejecutar la operacion.",
        "410": "Recurso retirado o ya no disponible.",
        "422": "Entidad bien formada pero semanticamente invalida para la regla aplicada.",
        "429": "Limite de tasa excedido; reintentar segun politicas de rate limit.",
        "500": "Error interno del servidor sin exposicion de detalles sensibles.",
        "503": "Servicio temporalmente no disponible (dependencia o base de datos).",
    }
    return mapping.get(str(code), "Respuesta de error documentada para esta operacion.")


def generate_operation_id(method: str, path: str) -> str:
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", path) if t and t != "api"]
    camel = "".join(token.capitalize() for token in tokens)
    return f"{method.lower()}{camel}"


def build_description(path: str, method: str, path_item: dict, op: dict, contract: dict, tag: str) -> str:
    path_params = collect_parameters(path_item, op, "path")
    query_params = collect_parameters(path_item, op, "query")
    header_params = collect_parameters(path_item, op, "header")

    request_body = op.get("requestBody") or {}
    body_required = bool(request_body.get("required")) if isinstance(request_body, dict) else False
    body_content = sorted((request_body.get("content") or {}).keys()) if isinstance(request_body, dict) else []

    responses = op.get("responses") or {}
    success_codes = sorted([c for c in responses if c.isdigit() and int(c) < 400]) or ["200"]
    error_codes = sorted([c for c in responses if c.isdigit() and int(c) >= 400]) or ["400", "401", "403", "404", "500"]

    security = op.get("security")
    roles = op.get("x-roles") or []
    if security in (None, []):
        sec_line = "Endpoint publico; no requiere token JWT."
    else:
        schemes = []
        for item in security:
            if isinstance(item, dict):
                schemes.extend(item.keys())
        sec_line = f"Requiere esquema(s) de seguridad: {', '.join(sorted(set(schemes)))}."
    if roles:
        sec_line += f" Roles requeridos: {', '.join(roles)}."

    actor = {
        "Admin": "Administrador de plataforma o equipo de backoffice.",
        "Users": "Administrador autenticado en gestion legacy de usuarios.",
        "QuestionnaireRuntimeAdmin": "Administrador funcional del runtime v1.",
        "QuestionnaireRuntime": "Usuario autenticado, profesional o actor operativo del runtime v1.",
        "QuestionnaireV2": "Frontend autenticado del flujo de cuestionarios v2.",
        "Dashboard": "Frontend/backoffice autenticado para analitica operacional.",
        "Reports": "Frontend/backoffice autenticado para generar reportes.",
        "Auth": "Clientes de autenticacion (frontend o integraciones seguras).",
        "MFA": "Usuario autenticado en flujo de seguridad MFA.",
        "Email": "Usuario final o cliente de soporte para unsubscribe.",
        "ProblemReports": "Usuario autenticado o administrador de soporte.",
        "Predict": "Integracion tecnica experimental (no contrato principal).",
        "Health": "Operaciones, monitoreo y despliegue.",
        "Docs": "Integradores, QA y desarrollo para discovery de contrato.",
        "Evaluations": "Cliente autenticado que inicia evaluaciones v1.",
        "Questionnaires": "Administrador o cliente legacy de cuestionarios v1.",
    }.get(tag, "Cliente autenticado segun el modulo funcional.")

    input_lines = [
        f"- Metodo y ruta: `{method.upper()} {path}`.",
        f"- Parametros de ruta: {', '.join(path_params) if path_params else 'no aplica'}.",
        f"- Query params: {', '.join(query_params) if query_params else 'no aplica'}.",
        f"- Headers adicionales: {', '.join(header_params) if header_params else 'no aplica'}.",
    ]
    if body_content:
        req = "obligatorio" if body_required else "opcional"
        input_lines.append(f"- Body `{req}` en: {', '.join(body_content)}.")
    else:
        input_lines.append("- Body: no aplica.")

    error_lines = [f"- `{code}`: {error_description(code)}" for code in error_codes]
    status_line = contract["status"]
    if contract.get("replaced_by"):
        status_line += f". Reemplazo recomendado: `{contract['replaced_by']}`."

    return "\n".join(
        [
            "**Objetivo funcional**",
            f"Este endpoint permite {action_verb(method, path).lower()} el recurso de `{infer_module(path)}`.",
            "",
            "**Cuando debe usarse**",
            f"Usalo cuando el flujo requiera invocar `{method.upper()} {path}` y mantener trazabilidad contractual.",
            "",
            "**Actor que lo consume**",
            actor,
            "",
            "**Seguridad aplicable**",
            f"- {sec_line}",
            "",
            "**Entrada esperada**",
            *input_lines,
            "",
            "**Resultado exitoso**",
            f"- Codigos de exito documentados: {', '.join(success_codes)}.",
            "- La respuesta representa el estado procesado por el backend y mantiene compatibilidad con el esquema documentado.",
            "",
            "**Errores posibles y causa funcional**",
            *error_lines,
            "",
            "**Estado contractual**",
            f"- `{status_line}`",
            f"- Motivo: {contract['reason']}",
            f"- Accion OpenAPI: {contract['openapi_action']}",
        ]
    )


def clean_response_descriptions(op: dict):
    responses = op.setdefault("responses", {})
    for code, response in responses.items():
        if not isinstance(response, dict) or "$ref" in response:
            continue
        desc = str(response.get("description") or "").strip()
        if not desc or desc.lower() in {"success", "ok"}:
            response["description"] = success_description(str(code)) if str(code).isdigit() and int(code) < 400 else error_description(str(code))
        content = (response.get("content") or {}).get("application/json")
        if not content:
            continue
        schema = content.get("schema") or {}
        if schema.get("type") == "object" and not schema.get("properties") and "$ref" not in schema:
            schema.setdefault(
                "description",
                "Objeto JSON de respuesta cuyo detalle depende del flujo operativo; revisar ejemplos y reglas del endpoint.",
            )
            schema.setdefault("additionalProperties", True)
            content["schema"] = schema


def ensure_tags(spec: dict):
    expected = {
        "Health": "Endpoints de salud, readiness y metricas operativas.",
        "Auth": "Autenticacion, registro, renovacion de token y sesion.",
        "MFA": "Flujos MFA (TOTP) para configuracion, confirmacion y desactivacion.",
        "Email": "Soporte de unsubscribe y salud de canal de correo.",
        "Admin": "Backoffice administrativo con controles de rol, auditoria y seguridad.",
        "Users": "Gestion legacy de usuarios v1 (compatibilidad).",
        "Questionnaires": "Questionnaires v1 legacy y operaciones de compatibilidad.",
        "Evaluations": "Creacion de evaluaciones v1 usando plantilla activa.",
        "Predict": "Ruta experimental heredada de prediccion.",
        "QuestionnaireRuntime": "Runtime v1 para flujos operativos de evaluacion.",
        "QuestionnaireRuntimeAdmin": "Gobierno administrativo runtime v1.",
        "QuestionnaireV2": "Contrato operativo principal de cuestionarios v2.",
        "Dashboard": "Endpoints de dashboards operativos de producto.",
        "Reports": "Generacion y gestion de reportes operativos.",
        "ProblemReports": "Registro y seguimiento de reportes de problema.",
        "Docs": "Documentacion OpenAPI y UI Swagger.",
        "Misc": "Endpoints no clasificados explicitamente.",
    }
    existing = {item.get("name"): item for item in spec.get("tags", []) if isinstance(item, dict)}
    tags = []
    for name, desc in expected.items():
        tags.append({"name": name, "description": existing.get(name, {}).get("description") or desc})
    spec["tags"] = tags


def ensure_info_description(spec: dict):
    info = spec.setdefault("info", {})
    info["description"] = (
        "API backend de CognIA para soporte de screening y alerta temprana en salud mental infantil (6 a 11 anos) en entorno academico simulado.\n\n"
        "Alcance funcional:\n"
        "- Auth JWT + MFA, usuarios/admin, cuestionarios v1/runtime v1/v2, dashboards, reportes y problem reports.\n"
        "- Contratos legacy documentados con estado contractual explicito.\n\n"
        "Caveat clinico:\n"
        "- La API genera alertas de riesgo para screening/apoyo profesional.\n"
        "- No es diagnostico clinico automatico ni definitivo.\n\n"
        "Seguridad:\n"
        "- JWT/cookies segun endpoint, CSRF en refresh y rate limits por endpoint critico.\n"
        "- Endpoints admin restringidos por rol ADMIN.\n"
        "- Errores endurecidos sin fuga de detalles sensibles."
    )


def build_runtime_inventory():
    app = create_app(TestingConfig)
    runtime_paths = defaultdict(set)
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = to_openapi_path(rule.rule)
        for method in sorted(rule.methods):
            ml = method.lower()
            if ml in HTTP_METHODS:
                runtime_paths[path].add(ml)
    return runtime_paths


def ensure_missing_questionnaire_legacy_ops(paths: dict):
    if "/api/v1/questionnaires/{template_id}/activate" not in paths:
        paths["/api/v1/questionnaires/{template_id}/activate"] = {
            "parameters": [
                {
                    "name": "template_id",
                    "in": "path",
                    "required": True,
                    "description": "ID del template legacy a activar.",
                    "schema": {"type": "string"},
                }
            ],
            "post": {
                "tags": ["Questionnaires"],
                "summary": "Activar template legacy v1",
                "operationId": "postApiV1QuestionnairesTemplateIdActivate",
                "deprecated": True,
                "x-contract-status": "KEEP_ACTIVE_BUT_LEGACY",
                "x-replaced-by": "/api/admin/questionnaires/{template_id}/publish",
                "security": [{"bearerAuth": []}],
                "x-roles": ["ADMIN"],
                "responses": {
                    "200": {
                        "description": "Template v1 activado correctamente.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/QuestionnaireTemplate"}}},
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            },
        }

    if "/api/v1/questionnaires/active/clone" not in paths:
        paths["/api/v1/questionnaires/active/clone"] = {
            "post": {
                "tags": ["Questionnaires"],
                "summary": "Clonar cuestionario activo legacy v1",
                "operationId": "postApiV1QuestionnairesActiveClone",
                "deprecated": True,
                "x-contract-status": "KEEP_ACTIVE_BUT_LEGACY",
                "x-replaced-by": "/api/admin/questionnaires/{template_id}/clone",
                "security": [{"bearerAuth": []}],
                "x-roles": ["ADMIN"],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/QuestionnaireCloneRequest"}}},
                },
                "responses": {
                    "201": {
                        "description": "Template clonado correctamente en flujo legacy.",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/QuestionnaireCloneResponse"}}},
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "409": {"$ref": "#/components/responses/Conflict"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            }
        }


def main():
    openapi_path = Path(PROJECT_ROOT) / "docs" / "openapi.yaml"
    matrix_path = Path(PROJECT_ROOT) / "docs" / "endpoint_lifecycle_matrix.md"

    spec = yaml.safe_load(openapi_path.read_text(encoding="utf-8"))
    ensure_info_description(spec)
    ensure_tags(spec)

    runtime = build_runtime_inventory()
    runtime_canonical = {canonical(p): p for p in runtime.keys()}

    paths = spec.setdefault("paths", {})
    normalized_paths = {}
    for spec_path, path_item in paths.items():
        target = runtime_canonical.get(canonical(spec_path), spec_path)
        if target not in normalized_paths:
            normalized_paths[target] = path_item
            continue
        for key, value in path_item.items():
            if key in HTTP_METHODS:
                normalized_paths[target][key] = value
            elif key == "parameters":
                normalized_paths[target].setdefault("parameters", [])
                normalized_paths[target]["parameters"].extend(value or [])
            else:
                normalized_paths[target][key] = value
    paths = normalized_paths

    ensure_missing_questionnaire_legacy_ops(paths)

    for runtime_path, methods in runtime.items():
        path_item = paths.setdefault(runtime_path, {})
        for method in methods:
            if method in path_item:
                continue
            tag = infer_tag(runtime_path)
            sec, roles = security_requirements(runtime_path)
            op = {
                "tags": [tag],
                "summary": f"{action_verb(method, runtime_path)} {runtime_path}",
                "operationId": generate_operation_id(method, runtime_path),
                "responses": {
                    "200": {
                        "description": success_description("200"),
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MessageResponse"}}},
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            }
            if sec:
                op["security"] = sec
            if roles:
                op["x-roles"] = roles
            path_item[method] = op

    lifecycle_rows = []
    used_operation_ids = set()

    for path in sorted(paths.keys()):
        path_item = paths[path]
        ensure_path_parameters(path, path_item)
        for method, op in list(path_item.items()):
            if method not in HTTP_METHODS or not isinstance(op, dict):
                continue
            tag = infer_tag(path)
            op["tags"] = [tag]

            sec, roles = security_requirements(path)
            if sec and "security" not in op:
                op["security"] = sec
            if roles:
                op["x-roles"] = roles

            contract = classify_contract(path)
            op["x-contract-status"] = contract["status"]
            if contract.get("replaced_by"):
                op["x-replaced-by"] = contract["replaced_by"]
            if contract["status"] in {"KEEP_ACTIVE_BUT_LEGACY", "DEPRECATE_PUBLIC"}:
                op["deprecated"] = True

            op["summary"] = op.get("summary") or f"{action_verb(method, path)} {path}"
            op_id = generate_operation_id(method, path)
            if op_id in used_operation_ids:
                i = 2
                while f"{op_id}{i}" in used_operation_ids:
                    i += 1
                op_id = f"{op_id}{i}"
            used_operation_ids.add(op_id)
            op["operationId"] = op_id

            op["description"] = build_description(path, method, path_item, op, contract, tag)
            clean_response_descriptions(op)

            clients = {
                "Admin": "backoffice/admin",
                "Users": "admin legacy",
                "QuestionnaireRuntime": "frontend runtime v1",
                "QuestionnaireRuntimeAdmin": "admin runtime v1",
                "QuestionnaireV2": "frontend cuestionario v2",
                "Dashboard": "analitica operativa",
                "Reports": "reporting",
                "ProblemReports": "usuarios + soporte",
                "Auth": "frontend auth",
                "MFA": "usuarios autenticados",
                "Email": "soporte de correo",
                "Predict": "integracion experimental",
                "Health": "operaciones",
                "Docs": "integradores/QA",
                "Questionnaires": "clientes legacy v1",
                "Evaluations": "clientes v1",
            }.get(tag, "consumidor autenticado")

            lifecycle_rows.append(
                {
                    "endpoint": f"{method.upper()} {path}",
                    "module": infer_module(path),
                    "replaced_by": contract.get("replaced_by") or "N/A",
                    "reason": contract["reason"],
                    "clients": clients,
                    "compat_risk": contract["compat_risk"],
                    "decision": contract["status"],
                    "openapi_action": contract["openapi_action"],
                }
            )

    spec["paths"] = dict(sorted(paths.items(), key=lambda x: x[0]))
    openapi_path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=False, width=120), encoding="utf-8")

    lines = [
        "# Matriz de reemplazo, deprecacion y cierre de endpoints",
        "",
        "Fuente: inventario runtime real (`api/app.py`) + contrato publicado (`docs/openapi.yaml`).",
        "",
        "| Endpoint actual | Modulo/version | Endpoint que lo reemplaza | Motivo de reemplazo o convivencia | Clientes/flujo afectados | Riesgo compatibilidad | Decision final | Accion OpenAPI |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(lifecycle_rows, key=lambda x: x["endpoint"]):
        lines.append(
            f"| `{row['endpoint']}` | `{row['module']}` | `{row['replaced_by']}` | {row['reason']} | {row['clients']} | {row['compat_risk']} | `{row['decision']}` | {row['openapi_action']} |"
        )
    matrix_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OpenAPI actualizado: {openapi_path}")
    print(f"Matriz de ciclo de vida: {matrix_path}")


if __name__ == "__main__":
    main()

