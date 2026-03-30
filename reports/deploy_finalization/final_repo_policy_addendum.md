# Final Repo Policy Addendum

Fecha: 2026-03-30

## Addendum definitivo repo + deploy

1. Modelos que SI se versionan para runtime
- `models/adhd_model.pkl`

2. Modelos que NO se versionan en repo de deploy
- Historicos, challengers y duplicados en `models/` no usados por runtime final.
- `artifacts/models/`
- `artifacts/versioned_models/`

3. Motivo de conservar binario minimo en repo
- El runtime actual carga directamente desde `models/`.
- Excluir todos los binarios rompe inferencia.
- Se elige simplicidad operativa y robustez para Docker/Render en esta iteracion.

4. Decision arquitectonica explicita
- No se usa DB como almacenamiento principal de binarios.
- No se introduce descarga externa obligatoria de modelos en build/boot en esta iteracion.

5. Mejora futura opcional (fuera de alcance actual)
- Object storage + descarga controlada con checksums y fallback.
