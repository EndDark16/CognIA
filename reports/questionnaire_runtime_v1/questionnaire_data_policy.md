# Questionnaire Runtime v1 - Pol?tica de datos

## Datos permitidos y almacenados
- Edad (`child_age_years`).
- Sexo asignado al nacer (`child_sex_assigned_at_birth`).
- Tipo de respondiente (`respondent_type`).
- Respuestas por pregunta, estado de evaluaci?n, timestamps, metadatos de runtime/modelo.
- Identificadores t?cnicos: `requested_by_user_id`, `reference_id`, `pin_hash`.

## Datos prohibidos (no almacenados por dise?o)
- Nombre real del ni?o.
- Documento de identidad.
- Direcci?n de casa/colegio.
- Fecha exacta de nacimiento.
- Datos de geolocalizaci?n, biometr?a, multimedia, redes sociales.
- Datos socioecon?micos/familiares sensibles no necesarios para inferencia.

## Consentimiento y disclaimers
- Consentimiento previo versionado (`consent_pre`).
- Disclaimer previo (`disclaimer_pre`), de resultados (`disclaimer_result`) y de PDF (`disclaimer_pdf`).
- Toda evaluaci?n referencia versiones exactas de estos textos.

