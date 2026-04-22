# Model Questionnaire Alignment
Fecha: 2026-03-30

## Estado de coherencia
- El estado metodologico final de dominios esta claro.
- El scope productivo final esta claro (`inference_v4` con 4 dominios activos y elimination en hold).
- Lo no resuelto es el acople runtime cuestionario -> inferencia -> resultado en la experiencia actual.

## Producto
- Alineacion parcial: dominios activos definidos, pero sin endpoint de resultado por evaluacion conectado al flujo de cuestionario.
- Necesidad clave: salida por dominio con probabilidad, risk band, confianza/evidencia y manejo de incertidumbre.

## Tesis
- Alineacion parcial: tesis incluye 5 dominios con caveat elimination, pero no existe capa API/UI integrada que lo exponga como flujo cerrado desde cuestionario.

## Implicacion de elimination en hold
- El diseno real debe contemplar dos vistas de alcance:
  1. producto (adhd/anxiety/conduct/depression),
  2. tesis/interno (incluye elimination con caveat).
- Esto impacta contrato de resultados, autorizacion y UX de visualizacion.
