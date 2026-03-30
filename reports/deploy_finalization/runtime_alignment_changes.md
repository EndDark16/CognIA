# Runtime Alignment Changes

Fecha: 2026-03-30

## Cambios aplicados
1. `.gitignore`
- Se agrego excepcion `!models/adhd_model.pkl`.
- Motivo: evitar romper runtime al excluir `*.pkl` globalmente.
- Impacto: se conserva solo el binario minimo requerido por el API actual.

2. `REPO_CONTENT_POLICY.md`
- Se actualizo para reflejar que `models/adhd_model.pkl` se versiona como excepcion de runtime.
- Se formalizo la decision arquitectonica: no DB para binarios y sin fetch externo obligatorio en esta iteracion.

3. `requirements.txt`
- `scikit-learn` actualizado a `1.7.1`.
- Motivo: alinear runtime con version de serializacion del modelo y evitar incompatibilidad por unpickle.
- Impacto: mejora estabilidad de deploy al instalar dependencias desde cero.

## Cambios NO aplicados
- No se modifico logica de inferencia/negocio.
- No se cambiaron metricas, estados finales ni scope metodologico.
- No se activo elimination en runtime productivo.
