# Questionnaire design implications

- Decision de estrategia: **C global**.
- Longitud esperada:
  - Si gana B: cuestionario base corto + backend con capa de derivacion/imputacion mas intensa.
  - Si gana C: cuestionario cuidador mas completo, menor dependencia de proxies debiles.

- No omitir: edad, sexo, bloques nucleares CBCL/SDQ y disponibilidad instrumental clave.
- Puede derivarse en backend: flags `has_*`, site/release, algunos proxies declarados y auditados.
- Missing permitido: campos no respondidos no criticos, con manejo explicito y trazable.
- No permitido: asumir equivalencia clinica fuerte self-report <-> caregiver-report sin etiquetado de aproximacion.

## Recomendacion operativa
- Mantener un cuestionario unico compatible con la ruta recomendada por dominio.
- Si hay hibrido, mantener contrato unico y resolver diferencias solo en backend/model runtime.
