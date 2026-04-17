from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

OPENAPI_PATH = Path('docs/openapi.yaml')

ERROR_MEANING = {
    '400': 'solicitud invalida o error de validacion de entrada',
    '401': 'falta de autenticacion valida o token no aceptado',
    '403': 'autenticado sin permiso suficiente o control CSRF/MFA no satisfecho',
    '404': 'recurso solicitado no encontrado o no visible para el actor',
    '409': 'conflicto de estado de negocio (duplicidad o transicion invalida)',
    '410': 'recurso eliminado logicamente o no disponible por retencion',
    '423': 'usuario temporalmente bloqueado por politicas de seguridad',
    '429': 'limite de tasa excedido por politicas de proteccion',
    '500': 'falla interna del servicio',
    '503': 'dependencia critica no disponible (readiness/db)',
}


def _norm(text: str) -> str:
    n = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in n if not unicodedata.combining(ch))


def _schema_name(schema_obj):
    if not schema_obj:
        return None
    if '$ref' in schema_obj:
        return schema_obj['$ref'].split('/')[-1]
    if 'allOf' in schema_obj:
        parts = [_schema_name(p) for p in schema_obj['allOf']]
        parts = [p for p in parts if p]
        return ' + '.join(parts) if parts else 'allOf'
    if 'oneOf' in schema_obj:
        parts = [_schema_name(p) for p in schema_obj['oneOf']]
        parts = [p for p in parts if p]
        return ' o '.join(parts) if parts else 'oneOf'
    if 'type' in schema_obj:
        if schema_obj['type'] == 'array':
            return f"array<{_schema_name(schema_obj.get('items')) or 'item'}>"
        return schema_obj['type']
    return None


def _ensure_missing_paths(spec: dict) -> None:
    paths = spec.setdefault('paths', {})
    if '/api/v1/questionnaires/{template_id}/activate' not in paths:
        paths['/api/v1/questionnaires/{template_id}/activate'] = {
            'post': {
                'tags': ['Questionnaires'],
                'x-roles': ['ADMIN'],
                'security': [{'bearerAuth': []}],
                'deprecated': True,
                'parameters': [
                    {
                        'in': 'path',
                        'name': 'template_id',
                        'required': True,
                        'schema': {'type': 'string', 'format': 'uuid'},
                    }
                ],
                'responses': {
                    '200': {
                        'description': 'Template activated',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/AdminTemplateActionResponse'}
                            }
                        },
                    },
                    '400': {'$ref': '#/components/responses/BadRequest'},
                    '401': {'$ref': '#/components/responses/Unauthorized'},
                    '403': {'$ref': '#/components/responses/Forbidden'},
                    '404': {'$ref': '#/components/responses/NotFound'},
                    '409': {'$ref': '#/components/responses/Conflict'},
                    '500': {'$ref': '#/components/responses/ServerError'},
                },
            }
        }

    if '/api/v1/questionnaires/active/clone' not in paths:
        paths['/api/v1/questionnaires/active/clone'] = {
            'post': {
                'tags': ['Questionnaires'],
                'x-roles': ['ADMIN'],
                'security': [{'bearerAuth': []}],
                'deprecated': True,
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/QuestionnaireCloneRequest'}
                        }
                    },
                },
                'responses': {
                    '201': {
                        'description': 'Template cloned',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/QuestionnaireCloneResponse'}
                            }
                        },
                    },
                    '400': {'$ref': '#/components/responses/BadRequest'},
                    '401': {'$ref': '#/components/responses/Unauthorized'},
                    '403': {'$ref': '#/components/responses/Forbidden'},
                    '404': {'$ref': '#/components/responses/NotFound'},
                    '409': {'$ref': '#/components/responses/Conflict'},
                    '500': {'$ref': '#/components/responses/ServerError'},
                },
            }
        }

    if '/api/admin/roles' in paths and 'post' not in paths['/api/admin/roles']:
        paths['/api/admin/roles']['post'] = {
            'tags': ['Admin'],
            'x-roles': ['ADMIN'],
            'security': [{'bearerAuth': []}],
            'requestBody': {
                'required': True,
                'content': {
                    'application/json': {
                        'schema': {'$ref': '#/components/schemas/AdminRoleCreateRequest'}
                    }
                },
            },
            'responses': {
                '201': {
                    'description': 'Role created',
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/AdminRoleItem'}
                        }
                    },
                },
                '400': {'$ref': '#/components/responses/BadRequest'},
                '401': {'$ref': '#/components/responses/Unauthorized'},
                '403': {'$ref': '#/components/responses/Forbidden'},
                '409': {'$ref': '#/components/responses/Conflict'},
                '500': {'$ref': '#/components/responses/ServerError'},
            },
        }

    if '/api/admin/impersonate/{user_id}' not in paths:
        paths['/api/admin/impersonate/{user_id}'] = {
            'post': {
                'tags': ['Admin'],
                'x-roles': ['ADMIN'],
                'security': [{'bearerAuth': []}],
                'parameters': [
                    {
                        'in': 'path',
                        'name': 'user_id',
                        'required': True,
                        'schema': {'type': 'string', 'format': 'uuid'},
                    }
                ],
                'responses': {
                    '200': {
                        'description': 'Impersonation token',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/AdminImpersonateResponse'}
                            }
                        },
                    },
                    '400': {'$ref': '#/components/responses/BadRequest'},
                    '401': {'$ref': '#/components/responses/Unauthorized'},
                    '403': {'$ref': '#/components/responses/Forbidden'},
                    '404': {'$ref': '#/components/responses/NotFound'},
                    '409': {'$ref': '#/components/responses/Conflict'},
                    '500': {'$ref': '#/components/responses/ServerError'},
                },
            }
        }


def _update_info_and_tags(spec: dict) -> None:
    spec.setdefault('info', {})['description'] = (
        'API backend de CognIA para screening y apoyo profesional en salud mental infantil (6 a 11 anos) '
        'en entorno simulado.\\n\\n'
        'Alcance funcional actual:\\n'
        '- Autenticacion/autorizacion (JWT, refresh cookie, RBAC, MFA).\\n'
        '- Cuestionarios v1 legacy, runtime v1 y operacional v2 (sesiones, historial, share, PDF).\\n'
        '- Gobierno administrativo de usuarios, roles, cuestionarios, evaluaciones y auditoria.\\n'
        '- Reportes de problema con adjuntos validados y trazabilidad.\\n'
        '- Dashboards y reportes operativos v2.\\n\\n'
        'Consideraciones metodologicas:\\n'
        '- El sistema entrega alertas de riesgo para tamizaje/apoyo profesional.\\n'
        '- No constituye diagnostico clinico automatico ni reemplaza criterio profesional.\\n\\n'
        'Seguridad principal:\\n'
        '- JWT para endpoints protegidos y refresh token rotativo en cookie HttpOnly.\\n'
        '- CSRF double-submit en flujos con cookies.\\n'
        '- MFA TOTP y politicas de hardening/rate limiting.\\n\\n'
        'Gobernanza de contrato:\\n'
        '- Fuente activa: docs/openapi.yaml.\\n'
        '- Validacion automatizada runtime vs OpenAPI en tests de contrato.'
    )

    tag_desc = {
        'Health': 'Salud del servicio, readiness de base de datos y metricas del proceso.',
        'Auth': 'Registro, login, refresh, logout y recuperacion de contrasena.',
        'MFA': 'Enrolamiento, confirmacion y desactivacion de autenticacion multifactor.',
        'Email': 'Desuscripcion de correos y cumplimiento de comunicaciones.',
        'Admin': 'Gobernanza administrativa y operaciones de supervision.',
        'Users': 'Gestion administrativa v1 de usuarios (compatibilidad legacy).',
        'Questionnaires': 'Plantillas de cuestionario v1 y endpoints legacy de compatibilidad.',
        'Evaluations': 'Creacion de evaluaciones v1 basadas en plantilla activa.',
        'Predict': 'Inferencia experimental heredada, no recomendada para nuevas integraciones.',
        'QuestionnaireRuntime': 'Flujo runtime v1 de evaluaciones y acceso profesional.',
        'QuestionnaireRuntimeAdmin': 'Gobierno runtime v1 de templates/versiones/secciones.',
        'QuestionnaireV2': 'Flujo operacional v2 de sesiones, historial, tags, share y PDF.',
        'Dashboard': 'Consultas de analitica y monitoreo operativo v2.',
        'Reports': 'Creacion de jobs de reporte operativo v2.',
        'Docs': 'Swagger UI y especificacion OpenAPI estatica.',
        'ProblemReports': 'Registro y gestion de reportes de problema.',
    }
    tags = spec.setdefault('tags', [])
    names = {t.get('name') for t in tags}
    for t in tags:
        name = t.get('name')
        if name in tag_desc:
            t['description'] = tag_desc[name]
    if 'ProblemReports' not in names:
        tags.append({'name': 'ProblemReports', 'description': tag_desc['ProblemReports']})

def _summary(method: str, path: str) -> str:
    method = method.upper()

    if path == '/healthz':
        return 'Verificar liveness del backend'
    if path == '/readyz':
        return 'Verificar readiness con base de datos'
    if path == '/metrics':
        return 'Consultar metricas internas del proceso'
    if path == '/api/predict':
        return 'Ejecutar inferencia experimental (legacy)'
    if path == '/docs':
        return 'Visualizar Swagger UI de CognIA'
    if path == '/openapi.yaml':
        return 'Descargar especificacion OpenAPI vigente'

    if path.startswith('/api/auth'):
        mapping = {
            '/api/auth/register': 'Registrar cuenta de usuario',
            '/api/auth/login': 'Autenticar usuario con credenciales',
            '/api/auth/login/mfa': 'Completar autenticacion MFA de login',
            '/api/auth/refresh': 'Renovar token de acceso con refresh cookie',
            '/api/auth/logout': 'Cerrar sesion y revocar refresh tokens',
            '/api/auth/me': 'Consultar perfil del usuario autenticado',
            '/api/auth/password/change': 'Cambiar contrasena del usuario autenticado',
            '/api/auth/password/forgot': 'Solicitar inicio de recuperacion de contrasena',
            '/api/auth/password/reset': 'Restablecer contrasena con token de recuperacion',
            '/api/auth/password/reset/verify': 'Validar token de recuperacion de contrasena',
        }
        if path in mapping:
            return mapping[path]

    if path.startswith('/api/mfa'):
        return {
            '/api/mfa/setup': 'Iniciar configuracion MFA TOTP',
            '/api/mfa/confirm': 'Confirmar MFA y emitir codigos de recuperacion',
            '/api/mfa/disable': 'Deshabilitar MFA con verificacion reforzada',
        }.get(path, 'Operar flujo MFA')

    if path.startswith('/api/email/unsubscribe'):
        return 'Procesar desuscripcion de correo' + (' one-click (POST)' if method == 'POST' else ' por enlace')

    if path.startswith('/api/problem-reports'):
        return 'Registrar reporte de problema' if method == 'POST' else 'Listar reportes de problema del usuario actual'

    if path.startswith('/api/admin/problem-reports'):
        if method == 'GET' and path.endswith('/{id}'):
            return 'Consultar detalle de reporte de problema'
        if method == 'PATCH':
            return 'Actualizar estado y notas de reporte de problema'
        return 'Listar reportes de problema para administracion'

    if path.startswith('/api/admin'):
        if path == '/api/admin/roles' and method == 'POST':
            return 'Crear rol de sistema'
        last = path.split('/')[-1]
        if '/users/' in path and method == 'PATCH':
            return 'Actualizar usuario desde administracion'
        if path.endswith('/password-reset'):
            return 'Forzar reinicio de contrasena de usuario'
        if path.endswith('/mfa/reset'):
            return 'Reiniciar estado MFA de usuario'
        if path.endswith('/roles') and method == 'POST':
            return 'Asignar roles a usuario'
        if path.endswith('/roles') and method == 'GET':
            return 'Listar roles disponibles del sistema'
        if path.endswith('/audit-logs'):
            return 'Consultar bitacora de auditoria'
        if path.endswith('/questionnaires'):
            return 'Listar cuestionarios para administracion'
        if path.endswith('/publish'):
            return 'Publicar plantilla de cuestionario'
        if path.endswith('/archive'):
            return 'Archivar plantilla de cuestionario'
        if path.endswith('/clone'):
            return 'Clonar plantilla de cuestionario'
        if path.endswith('/approve'):
            return 'Aprobar validacion profesional de psicologo'
        if path.endswith('/reject'):
            return 'Rechazar validacion profesional de psicologo'
        if '/evaluations' in path and method == 'GET':
            return 'Listar evaluaciones para supervision administrativa'
        if path.endswith('/status') and method == 'PATCH':
            return 'Actualizar estado administrativo de evaluacion'
        if path.endswith('/email/unsubscribes'):
            return 'Listar desuscripciones de correo'
        if path.endswith('/remove'):
            return 'Eliminar registro de desuscripcion'
        if path.endswith('/email/health'):
            return 'Consultar salud de configuracion de correo'
        if path.endswith('/metrics'):
            return 'Consultar snapshot administrativo de metricas'
        if '/impersonate/' in path:
            return 'Emitir token de impersonacion administrativa'
        return 'Ejecutar operacion administrativa'

    if path.startswith('/api/v1/users'):
        if method == 'GET' and path.endswith('/{user_id}'):
            return 'Consultar usuario v1 por identificador'
        if method == 'PATCH':
            return 'Actualizar usuario v1 por identificador'
        if method == 'DELETE':
            return 'Desactivar usuario v1 por identificador'
        if method == 'POST':
            return 'Crear usuario v1 (admin, legacy)'
        return 'Listar usuarios v1 (admin, legacy)'

    if path.startswith('/api/v1/questionnaires'):
        if path.endswith('/active') and method == 'GET':
            return 'Obtener plantilla activa de cuestionario v1'
        if path.endswith('/questions'):
            return 'Agregar preguntas a plantilla v1'
        if path.endswith('/activate'):
            return 'Activar plantilla v1 (legacy)'
        if path.endswith('/active/clone'):
            return 'Clonar plantilla activa v1 (legacy)'
        return 'Crear plantilla de cuestionario v1'

    if path.startswith('/api/v1/evaluations'):
        return 'Crear evaluacion v1 sobre plantilla activa'

    if path.startswith('/api/v1/questionnaire-runtime/admin'):
        if path.endswith('/bootstrap'):
            return 'Inicializar catalogo runtime v1'
        if path.endswith('/questions'):
            return 'Agregar preguntas a seccion runtime v1'
        if path.endswith('/templates') and method == 'POST':
            return 'Crear template runtime v1'
        if path.endswith('/active'):
            return 'Activar template runtime v1'
        if path.endswith('/versions') and method == 'GET':
            return 'Listar versiones de template runtime v1'
        if path.endswith('/versions') and method == 'POST':
            return 'Crear version de template runtime v1'
        if '/versions/' in path and method == 'GET':
            return 'Consultar detalle de version runtime v1'
        if path.endswith('/disclosures'):
            return 'Agregar disclosure a version runtime v1'
        if path.endswith('/publish'):
            return 'Publicar version runtime v1'
        if path.endswith('/sections'):
            return 'Agregar seccion a version runtime v1'

    if path.startswith('/api/v1/questionnaire-runtime'):
        if path.endswith('/questionnaire/active'):
            return 'Obtener cuestionario activo runtime v1'
        if path.endswith('/evaluations/draft') and method == 'POST':
            return 'Crear borrador de evaluacion runtime v1'
        if path.endswith('/evaluations/history'):
            return 'Listar historial de evaluaciones runtime v1'
        if path.endswith('/draft') and method == 'PATCH':
            return 'Guardar respuestas parciales de borrador runtime v1'
        if path.endswith('/export'):
            return 'Exportar evaluacion runtime v1'
        if path.endswith('/heartbeat'):
            return 'Registrar heartbeat de evaluacion runtime v1'
        if path.endswith('/responses') and '/professional/' in path:
            return 'Consultar respuestas con acceso profesional runtime v1'
        if path.endswith('/responses'):
            return 'Consultar respuestas de evaluacion runtime v1'
        if path.endswith('/results') and '/professional/' in path:
            return 'Consultar resultados con acceso profesional runtime v1'
        if path.endswith('/results'):
            return 'Consultar resultados de evaluacion runtime v1'
        if path.endswith('/status'):
            return 'Consultar estado de evaluacion runtime v1'
        if path.endswith('/submit'):
            return 'Enviar evaluacion runtime v1 para procesamiento'
        if path.endswith('/validate-section'):
            return 'Validar completitud de seccion runtime v1'
        if path.endswith('/notifications'):
            return 'Listar notificaciones runtime v1'
        if path.endswith('/read'):
            return 'Marcar notificacion runtime v1 como leida'
        if path.endswith('/professional/access'):
            return 'Abrir acceso profesional a evaluacion runtime v1'
        if path.endswith('/access') and method == 'DELETE':
            return 'Revocar acceso profesional a evaluacion runtime v1'
        if path.endswith('/tag'):
            return 'Etiquetar evaluacion en flujo profesional runtime v1'
        if method == 'DELETE' and '/evaluations/' in path:
            return 'Eliminar logicamente evaluacion runtime v1'

    if path.startswith('/api/v2/dashboard'):
        base = path.split('/')[-1].replace('-', ' ')
        return f'Consultar {base} en dashboard operativo v2'

    if path.startswith('/api/v2/reports/jobs'):
        return 'Crear job de reporte operacional v2'

    if path.startswith('/api/v2/questionnaires'):
        if path.endswith('/active'):
            return 'Obtener cuestionario activo v2 paginado'
        if path.endswith('/admin/bootstrap'):
            return 'Ejecutar bootstrap administrativo de cuestionario v2'
        if path.endswith('/history'):
            return 'Listar historial de sesiones v2'
        if '/history/' in path and path.endswith('/results'):
            return 'Consultar resultados historicos de sesion v2'
        if '/history/' in path and path.endswith('/pdf'):
            return 'Consultar metadata del PDF de sesion v2'
        if '/history/' in path and path.endswith('/pdf/download'):
            return 'Descargar PDF de sesion v2'
        if '/history/' in path and path.endswith('/pdf/generate'):
            return 'Generar PDF de sesion v2'
        if '/history/' in path and path.endswith('/share'):
            return 'Crear codigo de comparticion para sesion v2'
        if '/history/' in path and path.endswith('/tags') and method == 'POST':
            return 'Asignar etiqueta a sesion v2'
        if '/history/' in path and '/tags/' in path and method == 'DELETE':
            return 'Eliminar etiqueta de sesion v2'
        if '/sessions' in path and method == 'POST':
            return 'Crear sesion de cuestionario v2'
        if '/sessions/' in path and path.endswith('/answers'):
            return 'Guardar respuestas parciales de sesion v2'
        if '/sessions/' in path and path.endswith('/page'):
            return 'Consultar pagina de sesion v2'
        if '/sessions/' in path and path.endswith('/submit'):
            return 'Enviar sesion v2 para procesamiento final'
        if '/sessions/' in path and method == 'GET':
            return 'Consultar sesion de cuestionario v2'
        if '/history/' in path and method == 'GET':
            return 'Consultar detalle historico de sesion v2'
        if '/shared/' in path:
            return 'Acceder a resultados compartidos de cuestionario v2'

    verb = {'GET': 'Consultar', 'POST': 'Ejecutar', 'PATCH': 'Actualizar', 'DELETE': 'Eliminar', 'PUT': 'Reemplazar'}.get(method, 'Operar')
    return f'{verb} recurso de API'


def _make_operation_id(summary: str, used: set[str]) -> str:
    words = re.sub(r'[^a-z0-9]+', ' ', _norm(summary).lower()).strip().split()
    stop = {'de', 'del', 'la', 'el', 'los', 'las', 'para', 'con', 'por', 'y', 'v1', 'v2'}
    words = [w for w in words if w not in stop]
    if not words:
        words = ['operacion']
    op_id = words[0] + ''.join(w.capitalize() for w in words[1:])
    base = op_id
    idx = 2
    while op_id in used:
        op_id = f'{base}{idx}'
        idx += 1
    used.add(op_id)
    return op_id


def actor_for(path_key: str) -> str:
    if path_key.startswith('/api/admin'):
        return 'Administrador del sistema con rol ADMIN y sesion autenticada.'
    if '/professional/' in path_key:
        return 'Psicologo autorizado (o administrador con permisos equivalentes) en flujo profesional.'
    if path_key.startswith('/api/v2/dashboard') or path_key.startswith('/api/v2/reports'):
        return 'Equipo operativo/analitica autenticado para monitoreo y reportes.'
    if path_key.startswith('/api/v2/questionnaires/shared'):
        return 'Consumidor externo con identificador de cuestionario y share code validos.'
    if path_key.startswith('/api/problem-reports'):
        return 'Usuario autenticado que reporta incidentes del producto.'
    if path_key.startswith('/api/v1/questionnaire-runtime/admin'):
        return 'Administrador funcional del runtime v1 con permisos de gobierno de templates/versiones.'
    if path_key.startswith('/api/v1/questionnaire-runtime'):
        return 'Usuario autenticado del flujo runtime v1 (cuidador/psicologo segun endpoint).'
    if path_key.startswith('/api/v2/questionnaires'):
        return 'Usuario autenticado que opera sesiones, historial y resultados del cuestionario v2.'
    if path_key.startswith('/api/auth'):
        return 'Frontend de autenticacion y usuario final durante ciclo de acceso y recuperacion.'
    if path_key.startswith('/api/mfa'):
        return 'Usuario autenticado en proceso de habilitar o administrar MFA.'
    if path_key.startswith('/api/email/unsubscribe'):
        return 'Servicio de correo, cliente web o usuario final mediante enlace/token de desuscripcion.'
    if path_key.startswith('/api/v1/users'):
        return 'Administrador usando endpoints v1 mantenidos por compatibilidad legacy.'
    if path_key.startswith('/api/v1/questionnaires'):
        return 'Administrador de contenidos de cuestionario en API v1 (compatibilidad legacy).'
    if path_key.startswith('/api/v1/evaluations'):
        return 'Usuario autenticado que registra una evaluacion v1 con respuestas estructuradas.'
    if path_key in {'/healthz', '/readyz', '/metrics'}:
        return 'Infraestructura, observabilidad y operaciones de plataforma.'
    if path_key in {'/docs', '/openapi.yaml'}:
        return 'Desarrolladores, QA e integradores que consultan contrato y UI de API.'
    if path_key == '/api/predict':
        return 'Consumo tecnico experimental para pruebas de inferencia heredada.'
    return 'Consumidor autenticado conforme al control de acceso declarado por el endpoint.'


def _security_text(path_key: str, op: dict) -> str:
    sec = op.get('security')
    roles = op.get('x-roles')
    role_text = f" Roles requeridos documentados: {', '.join(roles)}." if roles else ''
    if not sec:
        return 'No declara esquema de autenticacion obligatorio en OpenAPI; puede ser publico segun configuracion.' + role_text

    labels = []
    for item in sec:
        if not item:
            labels.append('acceso anonimo permitido segun configuracion')
            continue
        for key in item.keys():
            labels.append(
                {
                    'bearerAuth': 'JWT Bearer de acceso valido',
                    'cookieAuth': 'cookie refresh_token',
                    'csrfCookie': 'cookie csrf_refresh_token',
                    'csrfHeader': 'header X-CSRF-Token',
                    'metricsToken': 'token de metricas en Authorization',
                    'mfaEnrollmentToken': 'token temporal de enrolamiento MFA',
                }.get(key, f'esquema {key}')
            )
    labels = list(dict.fromkeys(labels))
    return 'Requiere: ' + '; '.join(labels) + '.' + role_text


def _params_text(spec: dict, op: dict) -> str:
    comp = spec.get('components', {}).get('parameters', {})
    buckets = {'path': [], 'query': [], 'header': [], 'cookie': []}
    for p in op.get('parameters', []) or []:
        pobj = comp.get(p['$ref'].split('/')[-1], {}) if '$ref' in p else p
        where = pobj.get('in', 'query')
        name = pobj.get('name', 'parametro')
        req = 'obligatorio' if pobj.get('required') else 'opcional'
        sch = pobj.get('schema') or {}
        t = _schema_name(sch) or sch.get('format') or sch.get('type') or 'valor'
        buckets.setdefault(where, []).append(f'{name} ({req}, tipo {t})')
    out = []
    for where, label in [('path', 'Ruta'), ('query', 'Query'), ('header', 'Headers'), ('cookie', 'Cookies')]:
        vals = buckets.get(where) or []
        out.append(f"- {label}: {'; '.join(vals)}." if vals else f'- {label}: sin parametros declarados en este contrato.')
    return '\\n'.join(out)


def _body_text(op: dict) -> str:
    rb = op.get('requestBody')
    if not rb:
        return 'No aplica body en este endpoint segun la especificacion.'
    req = 'obligatorio' if rb.get('required') else 'opcional'
    parts = []
    for ctype, cobj in (rb.get('content') or {}).items():
        parts.append(f"{ctype} usando {_schema_name((cobj or {}).get('schema')) or 'schema por confirmar'}")
    return f"Body {req}. Tipos de contenido esperados: {'; '.join(parts)}." if parts else f'Body {req}.'


def _success_text(op: dict) -> str:
    parts = []
    for code, resp in (op.get('responses') or {}).items():
        c = str(code)
        if not re.match(r'^2\d\d$', c):
            continue
        desc = resp.get('description', 'respuesta exitosa') if isinstance(resp, dict) else 'respuesta exitosa'
        schemas = []
        if isinstance(resp, dict):
            for cobj in (resp.get('content') or {}).values():
                s = _schema_name((cobj or {}).get('schema'))
                if s:
                    schemas.append(s)
        schemas = list(dict.fromkeys(schemas))
        parts.append(f"{c}: {desc}" + (f" (estructura: {', '.join(schemas)})" if schemas else ''))
    return '; '.join(parts) + '.' if parts else 'No tiene codigos 2xx documentados; revisar contrato.'


def _error_text(op: dict) -> str:
    errors = []
    for code in (op.get('responses') or {}).keys():
        c = str(code)
        if re.match(r'^[45]\d\d$', c):
            errors.append(f"{c} ({ERROR_MEANING.get(c, 'error operacional documentado')})")
    return '; '.join(errors) + '.' if errors else 'No declara errores 4xx/5xx adicionales fuera de manejadores globales.'


def _classification(path_key: str, op: dict) -> str:
    c = []
    if op.get('deprecated'):
        c.append('legacy/deprecated')
    if path_key.startswith('/api/admin'):
        c.append('admin')
    if path_key.startswith('/api/v1'):
        c.append('versionado-v1')
    if path_key.startswith('/api/v2'):
        c.append('versionado-v2')
    if path_key.startswith('/api/v1/questionnaire-runtime'):
        c.append('runtime-cuestionario-v1')
    if path_key.startswith('/api/v2/questionnaires'):
        c.append('runtime-cuestionario-v2')
    if path_key.startswith('/api/v2/dashboard'):
        c.append('dashboard-operativo')
    if path_key.startswith('/api/v2/reports'):
        c.append('reporting-operativo')
    if path_key in {'/docs', '/openapi.yaml'}:
        c.append('documentacion-operativa')
    if path_key == '/api/predict':
        c.append('experimental')
    if not c:
        c.append('publico' if not op.get('security') else 'autenticado')
    return ', '.join(c)


def run() -> None:
    spec = yaml.safe_load(OPENAPI_PATH.read_text(encoding='utf-8'))
    _ensure_missing_paths(spec)
    _update_info_and_tags(spec)

    used_ids: set[str] = set()
    for pth, item in spec.get('paths', {}).items():
        for m in ['get', 'post', 'put', 'patch', 'delete', 'options', 'head', 'trace']:
            op = item.get(m)
            if not op:
                continue
            method = m.upper()
            summary = _summary(method, pth)
            op['summary'] = summary
            op['operationId'] = _make_operation_id(summary, used_ids)

            when = {
                'GET': 'Usar cuando necesites lectura o consulta del estado actual sin mutar el recurso.',
                'POST': 'Usar cuando necesites crear recurso o ejecutar una accion de negocio.',
                'PATCH': 'Usar cuando necesites actualizar parcialmente un recurso existente.',
                'DELETE': 'Usar cuando necesites revocar/eliminar logicamente un recurso.',
                'PUT': 'Usar cuando necesites reemplazar la representacion del recurso.',
            }.get(method, 'Usar segun el flujo operativo definido para este endpoint.')

            behavior = []
            if method == 'GET':
                behavior.append('Operacion de lectura; no debe mutar estado de negocio salvo telemetria tecnica.')
            else:
                behavior.append('Operacion potencialmente mutante sobre estado de negocio.')
            if '/submit' in pth:
                behavior.append('Dispara transicion de workflow y puede activar procesamiento/inferencia.')
            if '/heartbeat' in pth:
                behavior.append('Actualiza presencia/actividad de sesion.')
            if '/pdf/generate' in pth:
                behavior.append('Genera artefacto PDF para consulta/descarga posterior.')
            if '/pdf/download' in pth:
                behavior.append('Retorna archivo adjunto si existe artefacto y autorizacion.')
            if '/share' in pth:
                behavior.append('Gestiona acceso compartido sujeto a vigencia y controles de permiso.')
            if '/bootstrap' in pth:
                behavior.append('Sincroniza catalogos base; uso operacional controlado.')
            if pth == '/api/predict':
                behavior.append('Endpoint experimental y no recomendado para nuevas integraciones.')

            persistence = (
                'No modifica persistencia de negocio de forma directa; responde datos de consulta.'
                if method == 'GET' and pth not in {'/metrics', '/healthz', '/readyz'}
                else 'Puede crear/actualizar estado persistido y dejar trazabilidad de workflow/auditoria.'
            )
            if method == 'DELETE':
                persistence = 'Impacta estado persistido mediante desactivacion/eliminacion logica segun reglas del servicio.'
            if pth in {'/metrics', '/healthz', '/readyz', '/docs', '/openapi.yaml'}:
                persistence = 'Sin persistencia de negocio; endpoint de salud/observabilidad/documentacion.'

            caveats = []
            if op.get('deprecated'):
                caveats.append('Marcado como deprecated por compatibilidad; planificar migracion.')
            if pth in {'/docs', '/openapi.yaml'}:
                caveats.append('Disponible solo cuando SWAGGER_ENABLED esta habilitado en entorno.')
            if pth == '/metrics':
                caveats.append('Puede requerir token si METRICS_TOKEN_REQUIRED esta activo.')
            if '/shared/' in pth:
                caveats.append('Sujeto a rate limit y validez de share code.')

            desc = (
                f"**Objetivo funcional real:** {summary}.\\n\\n"
                f"**Recurso/proceso que gestiona:** `{method} {pth}`.\\n"
                f"**Cuando debe usarse:** {when}\\n"
                f"**Actor o rol que suele consumirlo:** {_summary('GET', pth) if pth in {'/docs','/openapi.yaml'} else ''}"  # placeholder removed below
            )
            desc = desc.replace(
                "**Actor o rol que suele consumirlo:** " + (_summary('GET', pth) if pth in {'/docs','/openapi.yaml'} else ''),
                f"**Actor o rol que suele consumirlo:** {actor_for(pth)}"
            )
            desc += (
                f"\\n**Seguridad aplicable:** {_security_text(pth, op)}\\n\\n"
                "**Parametros de entrada:**\\n"
                f"{_params_text(spec, op)}\\n\\n"
                f"**Body de solicitud:** {_body_text(op)}\\n\\n"
                f"**Comportamiento esperado del endpoint:** {' '.join(behavior)}\\n\\n"
                f"**Respuesta exitosa y significado funcional:** {_success_text(op)}\\n"
                f"**Errores posibles documentados:** {_error_text(op)}\\n"
                f"**Persistencia / workflow / trazabilidad:** {persistence}\\n"
                f"**Clasificacion del endpoint:** {_classification(pth, op)}."
            )
            if caveats:
                desc += "\\n**Caveats y restricciones relevantes:** " + ' '.join(caveats)
            op['description'] = desc

    OPENAPI_PATH.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=False, width=110), encoding='utf-8')


if __name__ == '__main__':
    run()
    print('ok')
