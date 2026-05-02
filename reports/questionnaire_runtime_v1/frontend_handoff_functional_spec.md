# Frontend handoff - Especificaci?n funcional

## Pantallas requeridas
1. Inicio + consentimiento/disclaimer previo.
2. Cuestionario multipaso por secciones.
3. Estado de procesamiento.
4. Resultado (usuario).
5. Historial de evaluaciones.
6. Detalle de evaluaci?n.
7. Acceso profesional por referencia+PIN.

## Reglas UX clave
- Guardado parcial y reanudaci?n obligatorios.
- Heartbeat durante `processing` para evitar notificaci?n innecesaria.
- Si usuario abandona pantalla, backend emite notificaci?n al completar.
- Elimination visible en resultados con `model_status` y caveat.

## Exportaci?n
- Modos: `responses_only`, `results_only`, `responses_and_results`.

