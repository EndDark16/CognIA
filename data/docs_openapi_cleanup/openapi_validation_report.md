# OpenAPI Validation Report

- spec: `docs/openapi.yaml`
- yaml_valid=yes
- openapi_version=3.0.3
- openapi_version_valid=yes
- duplicate_keys=0
- broken_refs=0
- duplicate_operation_ids=0
- duplicate_paths=0
- swagger_renderable=yes
- equivalent_validation_pass=yes
- tools_used=ruamel.yaml, openapi-spec-validator

## Errores encontrados
- Ninguno (estado final: validacion estructural en verde).

## Correcciones aplicadas
- Se removio autenticacion obligatoria en GET /api/v2/security/transport-key para habilitar bootstrap publico de clave de transporte.
- Se agrego rate limit dedicado para transport-key con QV2_TRANSPORT_KEY_RATE_LIMIT.
- Se reforzo contrato de transporte cifrado con invalid_crypto_version en endpoints sensibles v2.
- Se actualizaron descripciones/seguridad en OpenAPI para reflejar comportamiento real del runtime.
