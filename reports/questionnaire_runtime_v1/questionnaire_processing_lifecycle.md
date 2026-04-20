# Questionnaire Runtime v1 - Ciclo de procesamiento

## Estados
- `draft`: edici?n incremental.
- `submitted`: env?o confirmado.
- `processing`: inferencia en curso.
- `completed`: resultados persistidos.
- `failed`: error de procesamiento.
- `deleted_by_user`: borrado l?gico por propietario.

## Pipeline
1. Usuario crea draft.
2. Guarda respuestas parciales (`save draft`).
3. Valida secci?n opcionalmente.
4. Submit final (consentimiento requerido).
5. Se encola job (`qr_processing_job`).
6. Inferencia sobre 5 dominios.
7. Persistencia en `qr_domain_result`.
8. Notificaci?n si usuario no estaba en espera en vivo.

## Asincron?a
- Default: `QR_PROCESS_ASYNC=true` (executor en background).
- Testing: s?ncrono (`QR_PROCESS_ASYNC=false`) para determinismo.

