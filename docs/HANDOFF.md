# HANDOFF

## Resumen ejecutivo
Este proyecto es una tesis de ingeniería aplicada en salud mental infantil. El objetivo es sostener un sistema de alerta temprana para niños de 6 a 11 años, con salida por 5 dominios:

- ADHD
- Conduct
- Elimination
- Anxiety
- Depression

El enfoque es conservador y metodológicamente estricto:
- HBN es la base empírica.
- DSM-5 es el marco formal.
- El sistema tiene una capa interna diagnóstica exacta y una capa externa por dominios.
- El entorno es simulado.
- No debe presentarse como diagnóstico clínico definitivo.

## Estado actual por dominio
- ADHD: sólido.
- Anxiety: sólido.
- Conduct: sólido.
- Depression: sólido.
- Elimination: el dominio más difícil; sigue siendo el foco principal de mejora y validación estricta.

## Arquitectura / piezas visibles
Lo visible en el repositorio sugiere una plataforma con:
- modelos ML, principalmente Random Forest
- runtime de inferencia
- API/backend
- cuestionario real
- outputs para cuidador y psicólogo

Los outputs deben sostener, como mínimo:
- riesgo
- confianza
- incertidumbre
- caveats

## Riesgos abiertos
- Elimination sigue siendo el dominio más frágil.
- Existe riesgo de sobreprometer el alcance del sistema; debe mantenerse como screening/apoyo, no como diagnóstico automático.
- Cualquier cambio de contrato entre modelo, runtime y cuestionario puede romper consistencia si no se valida.
- Si algo no está confirmado en el repo, no debe asumirse: marcarlo como `por confirmar`.

## Decisiones metodológicas ya tomadas
- No vender el sistema como diagnóstico clínico definitivo.
- Priorizar robustez, honestidad y trazabilidad.
- Evitar leakage, shortcuts y equivalencias débiles entre fuentes.
- Mantener caveats explícitos en outputs y documentación.
- No romper artefactos históricos o contratos sin migración clara.

## Pendientes inmediatos
- Confirmar el artefacto de inferencia que está promovido como referencia operativa.
- Revisar la línea de Elimination antes de introducir más cambios de contrato u output.
- Verificar la alineación entre cuestionario, runtime y API.
- Confirmar qué artefactos están congelados y cuáles siguen experimentales.

## Qué revisar primero al retomar trabajo
1. `README.md`
2. `AGENTS_CONTEXT.md`
3. `docs/openapi.yaml`
4. `docs/OPENAPI_GUIDE.md`
5. Estado de `artifacts/inference_v4/` si aplica; si no está confirmado, tratarlo como `por confirmar`
6. Últimos reportes y artefactos de Elimination

## Por confirmar
- Versión exacta congelada del runtime final.
- Lista completa de artefactos definitivos vs experimentales.
- Cualquier contrato o versión posterior no reflejada en `README.md`.

## Estado operativo de Elimination
- Comparativa revisada: `elimination_clean_rebuild_v12` vs `elimination_final_push_v14`.
- Decision vigente en los reportes revisados: `KEEP_V12`.
- `v14` no desplaza a `v12` como linea de referencia operativa; tratarlo como experimental.
- Si se citan feature sets o thresholds de Elimination en futuras ventanas, confirmar primero si provienen del cierre `v12` o de una exploracion posterior.

## Cierre final de modelos
- Fuente de verdad para las versiones finales del enfoque dual: `data/questionnaire_final_ceiling_v4/reports/final_caregiver_closure_decision.md`, `data/questionnaire_final_ceiling_v4/reports/final_psychologist_closure_decision.md` y `data/questionnaire_final_ceiling_v4/reports/final_global_closure_decision.md`.
- Estos cierres cubren los dos modos: `cuidador` y `psicologo`.
- El cierre por dominio en `reports/final_closure/final_model_metrics_compact.csv` y `reports/final_closure/final_domain_status_matrix.csv` queda como linea historica de otra campana.
- `elimination` sigue siendo el dominio mas fragile y debe citarse con caveat incluso en el cierre final dual.
- El corte `v10+` aplica a la metodologia; la version concreta de cada modelo se lee en `data/final_closure_audit_v1/inventory/final_model_inventory.csv` como `model_version_final`. Si el artefacto no tiene version numerica explicita, anotarlo como `por confirmar`.

## Actualizacion de sesion (2026-04-06) - Final ceiling check v15
- IMPORTANTE: el bloque de techos de esta sesion queda como referencia obligatoria para el siguiente retome; no tratarlo como nota secundaria.
- Alcance ejecutado: verificacion final de techo por dominio y por modo, sin abrir campana nueva de mejora.
- Linea nueva creada: `data/final_ceiling_check_v15/` y `artifacts/final_ceiling_check_v15/`.
- Script fuente: `scripts/run_final_ceiling_check_v15.py`.
- Evidencia de outputs: `artifacts/final_ceiling_check_v15/final_ceiling_check_v15_manifest.json`.

Resultados centrales:
- Conteo de estado de techo (10 pares modo-dominio): `ceiling_reached=1`, `near_ceiling=8`, `marginal_room_left=1`, `meaningful_room_left=0`.
- `ceiling_reached`: `caregiver/depression`.
- `near_ceiling`: `caregiver/{adhd,anxiety,conduct,elimination}` + `psychologist/{adhd,conduct,depression,elimination}`.
- `marginal_room_left`: `psychologist/anxiety`.
- Elimination: se mantiene `KEEP_V12`, `uncertainty_preferred`, limite estructural y recomendacion de no seguir iterando salvo evidencia nueva.
- Conclusion global de tesis: el mayor retorno esperado esta en cierre de cuestionario/runtime/documentacion, no en una nueva iteracion amplia de modelado.

Archivos clave de esta pasada:
- `data/final_ceiling_check_v15/inventory/final_model_inventory.csv`
- `data/final_ceiling_check_v15/comparison/domain_version_progression.csv`
- `data/final_ceiling_check_v15/bootstrap/bootstrap_metric_intervals.csv`
- `data/final_ceiling_check_v15/stability/final_stability_matrix.csv`
- `data/final_ceiling_check_v15/tables/ceiling_status_matrix.csv`
- `data/final_ceiling_check_v15/reports/thesis_ceiling_conclusion.md`
- `data/final_ceiling_check_v15/reports/elimination_ceiling_analysis.md`

Pendientes abiertos (`por confirmar`):
- Identidad estricta cruzada entre campanas historicas en algunos enlaces de comparacion (marcado en `lineage_note`).
- Version exacta congelada del runtime final si no esta explicitamente auditada en artefacto versionado.

Regla de continuidad:
- Mantener `AGENTS.md` y `docs/HANDOFF.md` actualizados en cada sesion con decisiones, estado y pendientes para minimizar perdida de contexto.


## Actualizacion de sesion (2026-04-07) - Questionnaire master corrected
- Se creo `reports/questionnaire_design_inputs_v2/` con artefactos de inputs, requerimientos, terminologia, escalas, blueprint, cobertura por modo y readiness summary.
- Se genero `questionnaire_master_final_corrected.csv` desnormalizado y validado para uso en BD/runtime/API.
- Se publicaron `reports/questionnaire_master_final_audit_fix.md` y `reports/questionnaire_master_final_validation.csv`.
- Se aplico alcance final-only: `final_hardening_v10` (ADHD/Conduct/Anxiety/Depression) y `elimination_clean_rebuild_v12` (KEEP_V12 sobre v14).


## Actualizacion de sesion (2026-04-12) - Hybrid RF ceiling push v1
- Se completo una campana nueva de modelado y auditoria sobre `data/hybrid_dsm5_rebuild_v1/`.
- Linea creada: `data/hybrid_rf_ceiling_push_v1/`.
- Artefacto de cierre: `artifacts/hybrid_rf_ceiling_push_v1/hybrid_rf_ceiling_push_v1_manifest.json`.
- Script ejecutado: `scripts/run_hybrid_rf_ceiling_push_v1.py`.
- Cobertura: 30 pares (5 dominios x 6 modos).

Resultados operativos clave:
- Mejor modo global cuidador: `caregiver_full` (promedio).
- Mejor modo global psicologo: `psychologist_full` (promedio).
- Mejores por dominio observadas en combinaciones de modos distintas (ver `tables/hybrid_rf_mode_domain_final_metrics.csv`).
- Sobreentrenamiento: presente en subconjunto de pares, no uniforme (ver `reports/hybrid_rf_overfitting_audit.md`).
- Generalizacion: globalmente fuerte (26/30 pares con criterio estricto; ver `reports/hybrid_rf_generalization_audit.md`).
- Comparacion full-mode vs linea previa: mejora material en 7/10 pares comparables (`tables/hybrid_rf_vs_previous_fullmode_delta.csv`).
- Techo: combinacion de `ceiling_reached` y `marginal_room_left` sin evidencia de `meaningful_room_left` en esta corrida (ver `reports/hybrid_rf_ceiling_decision.md`).

Archivos de referencia inmediata:
- `data/hybrid_rf_ceiling_push_v1/reports/hybrid_rf_executive_summary.md`
- `data/hybrid_rf_ceiling_push_v1/reports/hybrid_rf_domain_mode_analysis.md`
- `data/hybrid_rf_ceiling_push_v1/tables/hybrid_rf_mode_domain_winners.csv`
- `data/hybrid_rf_ceiling_push_v1/tables/hybrid_rf_mode_domain_final_metrics.csv`
- `data/hybrid_rf_ceiling_push_v1/tables/hybrid_rf_mode_domain_delta_vs_baseline.csv`

Claim permitido:
- evidencia apta para screening/apoyo profesional en entorno simulado;
- no diagnostico automatico o definitivo.

## Actualizacion de sesion (2026-04-12) - Hybrid RF consolidation v2
- Se completo la campana de consolidacion final enfocada en candidatos: `data/hybrid_rf_consolidation_v2/`.
- Script: `scripts/run_hybrid_rf_consolidation_v2.py`.
- Manifest: `artifacts/hybrid_rf_consolidation_v2/hybrid_rf_consolidation_v2_manifest.json`.
- Cobertura auditada: 13 candidatos provisionales de la linea `hybrid_rf_ceiling_push_v1`.

Resultados centrales:
- Reproduccion material: `13/13` candidatos.
- Decisiones: `PROMOTE_WITH_CAVEAT=7`, `HOLD_FOR_TARGETED_FIX=6`, `REJECT_AS_PRIMARY=0`.
- Champions v2:
  - `adhd -> psychologist_full (PROMOTE_WITH_CAVEAT)`
  - `anxiety -> caregiver_full (PROMOTE_WITH_CAVEAT)`
  - `conduct -> psychologist_2_3 (PROMOTE_WITH_CAVEAT)`
  - `depression -> caregiver_2_3 (HOLD_FOR_TARGETED_FIX)`
  - `elimination -> caregiver_2_3 (PROMOTE_WITH_CAVEAT)`
- Sobreentrenamiento: evidencia parcial en `3/13` candidatos segun gaps.
- DSM-5: aporte material observado en `5/5` dominios evaluados en comparativa `clean_base_only` vs `hybrid_full`.

Artefactos de referencia inmediata:
- `data/hybrid_rf_consolidation_v2/tables/hybrid_rf_final_promotion_decisions.csv`
- `data/hybrid_rf_consolidation_v2/tables/hybrid_rf_final_champions.csv`
- `data/hybrid_rf_consolidation_v2/tables/hybrid_rf_2_3_vs_full_comparison.csv`
- `data/hybrid_rf_consolidation_v2/tables/hybrid_rf_dsm5_contribution_analysis.csv`
- `data/hybrid_rf_consolidation_v2/reports/hybrid_rf_final_promotion_report.md`
- `data/hybrid_rf_consolidation_v2/reports/hybrid_rf_executive_summary_v2.md`

## Actualizacion de sesion (2026-04-13) - Hybrid RF final ceiling push v3
- Campana completada en `data/hybrid_rf_final_ceiling_push_v3/`.
- Script: `scripts/run_hybrid_rf_final_ceiling_push_v3.py`.
- Manifest: `artifacts/hybrid_rf_final_ceiling_push_v3/hybrid_rf_final_ceiling_push_v3_manifest.json`.

Resultados operativos:
- Cobertura: 30 pares (5 dominios x 6 modos).
- Trials/fits: 2850.
- Winners: 30.
- Promocion: `PROMOTE_NOW=13`, `PROMOTE_WITH_CAVEAT=6`, `HOLD_FOR_TARGETED_FIX=8`, `REJECT_AS_PRIMARY=3`.
- Champions:
  - `adhd -> psychologist_full`
  - `anxiety -> caregiver_2_3`
  - `conduct -> psychologist_2_3`
  - `depression -> caregiver_full`
  - `elimination -> psychologist_2_3`
- Sobreentrenamiento parcial: 8/30.
- Generalizacion fuerte: 25/30.
- DSM-5 aporta ganancia material por dominio en analisis `hybrid_rf_dsm5_vs_cleanbase_analysis.csv`.

Archivos clave:
- `data/hybrid_rf_final_ceiling_push_v3/tables/hybrid_rf_final_ranked_models.csv`
- `data/hybrid_rf_final_ceiling_push_v3/tables/hybrid_rf_final_promotion_decisions.csv`
- `data/hybrid_rf_final_ceiling_push_v3/tables/hybrid_rf_final_champions.csv`
- `data/hybrid_rf_final_ceiling_push_v3/reports/hybrid_rf_executive_summary_v3.md`

## Actualizacion de sesion (2026-04-13) - Hybrid RF targeted fix v4
- Campana quirurgica completada en `data/hybrid_rf_targeted_fix_v4/`.
- Script: `scripts/run_hybrid_rf_targeted_fix_v4.py`.
- Manifest: `artifacts/hybrid_rf_targeted_fix_v4/hybrid_rf_targeted_fix_v4_manifest.json`.

Resultados operativos:
- Candidatos auditados: 17.
- Fits/arboles: `980` fits, `311700` arboles.
- Decisiones: `PROMOTE_WITH_CAVEAT=2`, `CEILING_CONFIRMED_NO_MATERIAL_GAIN=2`, `HOLD_FOR_FINAL_LIMITATION=12`, `REJECT_AS_PRIMARY=1`, `PROMOTE_NOW=0`.
- Mejoras materiales vs v3: 3 candidatos (`anxiety__caregiver_1_3`, `depression__caregiver_2_3`, `elimination__caregiver_1_3`).
- Sobreentrenamiento: evidencia parcial (si).
- Generalizacion global focal: aceptable (si), con heterogeneidad por candidato.
- Techo confirmado en candidatos: `elimination__caregiver_2_3`, `elimination__psychologist_2_3`.

Champions (v4 + carry-forward v3):
- `adhd -> psychologist_full` (v3)
- `anxiety -> caregiver_2_3` (v4)
- `conduct -> psychologist_2_3` (v3)
- `depression -> psychologist_2_3` (v4)
- `elimination -> psychologist_2_3` (v4)

Estado de cierre:
- No cerrar aun la fase principal completa de modelado: persisten limitaciones en Depression y modos cortos de ADHD/Elimination.
- Mantener claim de screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de sesion (2026-04-13) - Hybrid final freeze v1
- Se completo consolidacion final documental/operativa sin nueva campana de entrenamiento.
- Script ejecutado: `scripts/build_hybrid_final_freeze_v1.py`.
- Linea: `data/hybrid_final_freeze_v1/`.
- Manifest: `artifacts/hybrid_final_freeze_v1/hybrid_final_freeze_v1_manifest.json`.

Resultados:
- Champions consolidados: 30 pares dominio-modo.
- Origen final: 17 pares desde v4 + 13 pares carry-forward de v3.
- Distribucion de estados: `FROZEN_PRIMARY=9`, `FROZEN_WITH_CAVEAT=5`, `HOLD_FOR_LIMITATION=13`, `REJECT_AS_PRIMARY=1`, `CEILING_CONFIRMED_BEST_PRACTICAL_POINT=2`.
- Quality labels: `muy_bueno=14`, `aceptable=7`, `malo=9`, `bueno=0`.
- Inputs maestro exportados: 223 (`directos=180`, `transparent_derived=43`).
- Cobertura cuestionario consolidada con metadata de modos, roles, capa clean-base/DSM-5, directos/derivados, y prioridad.
- Caveats de fuente: dos archivos pedidos no existen con ese nombre exacto (`hybrid_input_audit_classification_final.csv`, `hybrid_dataset_final_registry_v1.csv`) y quedan `por_confirmar`.

## Actualizacion de sesion (2026-04-13) - Hybrid no external scores rebuild v2
- Se completo reconstruccion estricta sin scores externos precalculados (base principal nueva para comparacion/producto real).
- Script: `scripts/run_hybrid_no_external_scores_rebuild_v2.py`.
- Linea: `data/hybrid_no_external_scores_rebuild_v2/`.
- Manifest: `artifacts/hybrid_no_external_scores_rebuild_v2/hybrid_no_external_scores_rebuild_v2_manifest.json`.

Resultados operativos:
- Columnas removidas: 52 (incluye 28/28 columnas explicitamente prohibidas por gobernanza).
- Columnas retenidas (universo original limpio): 176 (`directas=152`, `transparent_derived=24`).
- Engineered internas generadas y retenidas en dataset final: 9 (`eng_*`).
- Cobertura por modo auditada: sin modos severamente empobrecidos.
- 30 pares dominio-modo reentrenados con RF y auditoria completa (calibration, thresholds, bootstrap, seed stability, ablation, stress).
- Comparacion global vs linea congelada anterior:
  - `delta_precision_mean=+0.00279`
  - `delta_recall_mean=-0.06096`
  - `delta_balanced_accuracy_mean=-0.02854`
  - `delta_pr_auc_mean=-0.01348`
  - `delta_brier_mean=+0.00333`
- Dominios que resistieron mejor: `anxiety`, `conduct`.
- Deterioro mas fuerte: `adhd`; deterioro relevante adicional: `elimination`, `depression`.

Gobernanza y estado de lineas:
- Lineas previas marcadas como historicas/no funcionales para linea primaria nueva en `inventory/previous_models_status_demoted.csv`:
  - `hybrid_rf_ceiling_push_v1`
  - `hybrid_rf_consolidation_v2`
  - `hybrid_rf_final_ceiling_push_v3`
  - `hybrid_rf_targeted_fix_v4`
  - `hybrid_final_freeze_v1`
- Claim permitido se mantiene: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de sesion (2026-04-13) - Hybrid no external scores boosted v3
- Campana focalizada para mejorar la linea limpia sin scores externos.
- Script: `scripts/run_hybrid_no_external_scores_boosted_v3.py`.
- Linea: `data/hybrid_no_external_scores_boosted_v3/`.
- Manifest: `artifacts/hybrid_no_external_scores_boosted_v3/hybrid_no_external_scores_boosted_v3_manifest.json`.

Resultados clave:
- Trials: 249 (focus en 13 pares prioritarios).
- Feature engineering interno v3 agregado: 18 features (`engv3_*`).
- Comparacion vs v2: mejora material en BA/PR-AUC/Recall en los 13 pares priorizados, con caidas de precision en varios casos.
- Familias que dominaron: HGB y ExtraTrees en ADHD/Elimination/Anxiety; CatBoost lidero en Depression caregiver_full en este run.
- Nota: boostings externos se ejecutaron en subset pesado por costo computacional.

## Actualizacion de sesion (2026-04-13) - Hybrid operational freeze v1
- Script: `scripts/build_hybrid_operational_freeze_v1.py`.
- Linea: `data/hybrid_operational_freeze_v1/`.
- Manifest: `artifacts/hybrid_operational_freeze_v1/hybrid_operational_freeze_v1_manifest.json`.

Resumen:
- Champions finales: 30 pares con clasificacion operativa.
- Overrides desde boosted_v3: 4 (depression caregiver_full, depression psychologist_full, elimination caregiver_1_3, elimination psychologist_1_3).
- Clasificacion: `ROBUST_PRIMARY=15`, `PRIMARY_WITH_CAVEAT=2`, `HOLD_FOR_LIMITATION=9`, `SUSPECT_EASY_DATASET_NEEDS_CAUTION=4`.
- Sobreentrenamiento marcado en 2 pares (depression caregiver_1_3 y psychologist_1_3) por gap train-val BA > 0.1 (v2).
- Casos de posible facilidad de dataset: Conduct (caregiver_2_3, caregiver_full, psychologist_2_3, psychologist_full) por metricas casi perfectas.

## Actualizacion de sesion (2026-04-13) - Hybrid active modes freeze v1
- Script: `scripts/build_hybrid_active_modes_freeze_v1.py`.
- Linea: `data/hybrid_active_modes_freeze_v1/`.
- Manifest: `artifacts/hybrid_active_modes_freeze_v1/hybrid_active_modes_freeze_v1_manifest.json`.

Resultados:
- Activacion total: 30 modelos activos para 30 pares dominio-modo (sin vacios).
- Distribucion de clase operativa:
  - `ACTIVE_HIGH_CONFIDENCE=15`
  - `ACTIVE_MODERATE_CONFIDENCE=6`
  - `ACTIVE_LOW_CONFIDENCE=0`
  - `ACTIVE_LIMITED_USE=9`
- Inputs maestro para cuestionario: 203 filas, con metadata de respondabilidad/modos/dominios y campos de scoring interno.
- Conteos de inputs: `directos=152`, `transparent_derived=51`, `requires_internal_scoring=51`.

## Actualizacion de sesion (2026-04-14) - Questionnaire backend operacional v2

Estado:
- Implementacion backend v2 completada para cuestionario operativo con sesiones por modo, inferencia por dominio, historial, tags, share code, PDF y dashboards/reportes.

Cambios principales:
- Migracion nueva: `migrations/versions/20260414_01_add_questionnaire_backend_v2.py`.
- API v2: `api/routes/questionnaire_v2.py` (base `/api/v2`).
- Servicios:
  - `api/services/questionnaire_v2_loader_service.py`
  - `api/services/questionnaire_v2_service.py`
- Schemas: `api/schemas/questionnaire_v2_schema.py`.
- Script de bootstrap/operacion: `scripts/bootstrap_questionnaire_backend_v2.py`.
- Registro en app: `api/app.py` agrega blueprint `questionnaire_v2_bp`.

Notas operativas:
- Bootstrap recomendado:
  1) `python scripts/bootstrap_questionnaire_backend_v2.py load-all`
  2) `python scripts/bootstrap_questionnaire_backend_v2.py regenerate-report-snapshot --months 12`
- Fuente de cuestionario consumida desde `data/cuestionario_v16.4/` con fallback a CSV visible cuando el master no existe con nombre exacto.
- Fuente de modelos consumida desde `data/hybrid_active_modes_freeze_v1/tables/hybrid_active_models_30_modes.csv`.
- Para algunos `active_model_id` la ruta de artefacto exacta queda `por_confirmar`; se aplica fallback trazable a champion por dominio.

Caveat metodologico:
- Mantener lenguaje de screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de sesion (2026-04-15) - Retiro de endpoints legacy v1 (questionnaires)

Decision aplicada:
- Se eliminaron del backend los endpoints:
  - `POST /api/v1/questionnaires/{template_id}/activate`
  - `POST /api/v1/questionnaires/active/clone`

Equivalentes activos:
- Publicar template: `POST /api/admin/questionnaires/{template_id}/publish`
- Clonar template: `POST /api/admin/questionnaires/{template_id}/clone`

Impacto y validacion:
- Se actualizaron referencias en `docs/openapi.yaml` y `README.md`.
- Se ajustaron pruebas que dependian de los endpoints retirados:
  - `tests/test_questionnaires.py`
  - `tests/test_evaluations.py`
- Resultado de regresion: `pytest -q` => `120 passed, 3 skipped`.

## Actualizacion de sesion (2026-04-15) - Problem reports + policy de artefactos

Implementacion backend:
- Nueva migracion: `migrations/versions/20260415_01_add_problem_reports.py`.
- Nuevas tablas:
  - `problem_reports`
  - `problem_report_attachments`
  - `problem_report_audit_events`
- Nuevas capas:
  - Route: `api/routes/problem_reports.py`
  - Service: `api/services/problem_report_service.py`
  - Schemas: `api/schemas/problem_report_schema.py`

Endpoints:
- `POST /api/problem-reports`
- `GET /api/problem-reports/mine`
- `GET /api/admin/problem-reports`
- `GET /api/admin/problem-reports/{id}`
- `PATCH /api/admin/problem-reports/{id}`

Documentacion/politica:
- `docs/problem_reporting_backend.md`
- `docs/api_full_reference.md`
- `docs/repository_artifact_policy.md`
- `docs/traceability_map.md`
- `docs/repository_maintenance.md`
- README renovado y `docs/openapi.yaml` actualizado.

Higiene de repo:
- Ajuste de `.gitignore` (uploads/runtime/generated noise).
- Normalizacion de `.gitattributes` para texto/binarios.

## Actualizacion (2026-04-16) - hotfix de arranque en Render
Incidente:
- El servicio caia al boot con `ModuleNotFoundError` en `api.routes.questionnaire_runtime` durante carga de `api/app.py`.

Accion aplicada:
- `api/app.py` actualizado para tratar `questionnaire_runtime` y `questionnaire_v2` como modulos opcionales:
  - import defensivo (`try/except`)
  - registro condicional de blueprints solo si el modulo esta disponible

Ramas/commits:
- `dev.enddark`: `ed5f57e` (`fix(startup): make questionnaire route imports optional`)
- `development`: `0067481` (promocion del fix para despliegue)

Resultado esperado:
- El backend inicia aunque esos modulos no esten presentes en la imagen desplegada, evitando caida total de Gunicorn.

## Actualizacion (2026-04-16) - cuestionarios runtime/v2 versionados completos
Problema detectado:
- Parte critica de cuestionarios/runtime/modelos existia en workspace local pero no en ramas remotas, por eso no aparecia en deploy.

Accion aplicada:
- Se versiono el bloque completo en `dev.enddark` (commit `96d3ffe`):
  - rutas `questionnaire_runtime` y `questionnaire_v2`
  - servicios runtime/v2 + schema v2
  - migraciones faltantes `20260330_01` y `20260414_01`
  - script `bootstrap_questionnaire_backend_v2.py`
  - datos fuente minimos del cuestionario y activacion de 30 modos
  - docs tecnicas de arquitectura/contratos/migracion/reporting
  - tests de API/servicios/smoke

Validacion tecnica:
- Docker Desktop:
  - `10 passed` en tests API/loader v2+runtime.
  - `4 passed` en tests model/smoke runtime.
- Alembic:
  - `alembic heads` resuelve en `20260415_01 (head)` (cadena consistente incluyendo `20260330_01` y `20260414_01`).

## Actualizacion (2026-04-16) - API hardening + OpenAPI runtime alignment
Resumen de la intervencion:
- Se alineo `docs/openapi.yaml` con el inventario real de endpoints registrados en runtime.
- Se incorporo cobertura de rutas `questionnaire_runtime` v1 y `questionnaire_v2` (incluye dashboards/reportes/docs).
- Se unifico criterio de contrato activo:
  - activo: `docs/openapi.yaml`
  - historico: `docs/archive/openapi/openapi_questionnaire_runtime_v1.yaml`

Cambios de seguridad aplicados:
- Carga de blueprints opcionales con politica fail-fast configurable en `api/app.py`:
  - `OPTIONAL_BLUEPRINTS_STRICT=true` (default)
  - `OPTIONAL_BLUEPRINTS_REQUIRED=questionnaire_runtime,questionnaire_v2`
- Eliminado leakage de `str(exc)` en respuestas 5xx de:
  - `api/routes/questionnaire_v2.py`
  - `api/routes/problem_reports.py`
- Shared access v2 endurecido:
  - rate limit (`QV2_SHARED_ACCESS_RATE_LIMIT`, default `30 per minute`)
  - validacion explicita de parametros (`SharedAccessSchema`)
- Descarga PDF v2 endurecida:
  - solo permite paths dentro de `artifacts/runtime_reports` (`resolve_download_path`)
- Upload de adjuntos problem reports endurecido:
  - validacion de firma binaria para PNG/JPEG/WEBP

DTOs/schemas normalizados:
- Nuevo `api/schemas/questionnaire_runtime_schema.py`.
- Runtime v1 ahora valida payloads en endpoints user/professional/admin.
- Admin clone valida request con `QuestionnaireCloneRequestSchema`.

Documentacion y estructura:
- README actualizado (estructura real, variables criticas nuevas, guardrail de contrato).
- `docs/OPENAPI_GUIDE.md` actualizado con regla de fuente activa + test de alineacion.
- `docs/api_full_reference.md` actualizado con naming real de params.
- `docs/repository_artifact_policy.md` y `docs/repository_maintenance.md` actualizados.
- Nueva evidencia: `docs/security_hardening_20260416.md`.

Guardrails/tests agregados o actualizados:
- `tests/contracts/test_openapi_runtime_alignment.py`
- `tests/api/test_app_blueprint_policy.py`
- `tests/api/test_questionnaire_v2_api.py` (hardening errores compartidos/PDF)
- `tests/test_problem_reports.py` (firma binaria adjuntos)
- `tests/api/test_questionnaire_runtime_api.py` (validacion payload runtime)

Verificacion ejecutada en esta ventana:
- `pytest tests/api/test_app_blueprint_policy.py tests/api/test_questionnaire_v2_api.py tests/api/test_questionnaire_runtime_api.py tests/test_problem_reports.py tests/contracts/test_openapi_runtime_alignment.py -q` => `23 passed`.

Pendiente inmediato:
- ejecutar `pytest -q` completo para cierre final de regresion de toda la base.

## Actualizacion de sesion (2026-04-17) - OpenAPI runtime alignment + hardening v2
- Se rehizo `docs/openapi.yaml` con alineacion total contra rutas runtime reales (`117/117` operaciones).
- Se agrego `scripts/openapi_professionalize.py` para normalizar contrato OpenAPI de forma reproducible.
- Se creo `docs/endpoint_lifecycle_matrix.md` con decision por endpoint/familia (keep, legacy, deprecate).
- Se corrigieron endpoints legacy faltantes en contrato:
  - `POST /api/v1/questionnaires/{template_id}/activate`
  - `POST /api/v1/questionnaires/active/clone`
- Seguridad endurecida:
  - `api/routes/predict.py`: validacion robusta, errores sanitizados, rate limit configurable.
  - `api/routes/questionnaire_v2.py`: metadata PDF sin `file_path`, solo `download_url`.
  - Nuevas variables: `PREDICT_RATE_LIMIT` en `config/settings.py` y `.env.example`.
- Guardrails agregados:
  - `tests/contracts/test_openapi_documentation_quality.py`
  - `tests/test_predict.py`
- `por confirmar`: resultado de `pytest -q` completo de esta ventana.

## Actualizacion (2026-04-17) - recovery de worktrees y fuente unica Swagger
Contexto:
- Se detecto estado de trabajo fragmentado por multiples worktrees con ruido local y potencial de confusion operativa.
- Se fijo como baseline canonico `origin/development`.

Auditoria:
- Inventario completo de worktrees auditado y clasificado.
- No se hallaron commits por delante de `origin/development` en los worktrees revisados.
- Worktrees secundarios con cambios locales mostraron diffs no sustantivos (line-ending churn) y se clasificaron `REJECT_AS_NOISY`.
- Detalle versionado en `docs/worktree_recovery_20260417.md`.

Proteccion no destructiva previa:
- Se exportaron snapshots de estado por worktree (status/diff/untracked) a respaldo local versionado.
- Se crearon tags de seguridad `safety/worktree_20260417_190150_*`.
- Se removieron worktrees obsoletos/noisy luego del respaldo, sin eliminar ramas ni trazabilidad.

Hardening documental/operativo aplicado:
- `.gitignore` ahora ignora `.worktrees/` para evitar contaminacion del arbol principal.
- README y `docs/repository_maintenance.md` actualizados con politica de rama canonica y gobernanza de worktrees.
- `docs/OPENAPI_GUIDE.md` reforzado para exigir que `/docs` consuma `/openapi.yaml` servido desde `docs/openapi.yaml`.
- Test nuevo: `tests/test_docs_metrics.py::test_swagger_openapi_source_of_truth_is_docs_openapi_yaml`.

Estado:
- Se mantiene `development` como fuente canonica operativa.
- OpenAPI activo sigue unificado en `docs/openapi.yaml` (sin fuentes paralelas activas).

## Actualizacion (2026-04-17) - recovery Alembic/DB y guardas contra 500
Auditoria Alembic/DB:
- `alembic current` confirmado en `20260415_01 (head)`.
- `alembic upgrade head` ejecutado sin pendientes.
- `alembic_version` en BD verificado en `20260415_01`.
- Comparativa ORM vs esquema real (tablas/columnas/indices/FK por definicion): sin faltantes.

Hallazgo de causa real del 500:
- El 500 reproducido en `GET /api/v1/questionnaire-runtime/questionnaire/active` no era por migraciones faltantes; era `FileNotFoundError` por artefactos de modelo ausentes (`models/champions/rf_*`) durante bootstrap de preguntas por defecto.

Correccion aplicada:
- `api/services/questionnaire_runtime_service.py`:
  - `_default_question_features()` ahora hace fallback seguro por dominio al contrato de features cuando faltan artefactos, evitando caida del endpoint de cuestionario activo.
- `api/routes/questionnaire_v2.py`:
  - manejo de excepciones backend reforzado para mapear dependencias/DB a `503 runtime_assets_unavailable` o `503 db_unavailable` (evita `500 internal_error` ambiguo).
- `api/routes/problem_reports.py`:
  - manejo de excepciones DB reforzado para devolver `503 db_unavailable` cuando corresponda.

Verificacion post-fix:
- `GET /api/admin/problem-reports` -> 200
- `GET /api/problem-reports/mine` -> 200
- `GET /api/v2/questionnaires/active` -> 200
- `GET /api/v1/questionnaire-runtime/questionnaire/active` -> 200
- Tests relevantes: `pytest tests/test_problem_reports.py tests/api/test_questionnaire_runtime_api.py tests/api/test_questionnaire_v2_api.py tests/contracts/test_openapi_runtime_alignment.py -q` -> `21 passed`.

Swagger/OpenAPI:
- `/openapi.yaml` sigue sirviendo `docs/openapi.yaml`.
- `/docs` sigue consumiendo esa spec.

## Actualizacion (2026-04-18) - openapi actualizado + smoke masivo de endpoints
Objetivo ejecutado:
- Se adopto el `docs/openapi.yaml` actualizado en workspace como contrato activo de Swagger.
- Se validaron todos los endpoints runtime registrados sin modificar seguridad persistente.

Ajustes de contrato OpenAPI:
- Se agregaron rutas faltantes en la spec para alinear runtime real:
  - `POST /api/admin/impersonate/{user_id}`
  - `POST /api/v1/questionnaires/active/clone`
  - `POST /api/v1/questionnaires/{template_id}/activate`
  - `POST /api/admin/roles`
- Validacion: `pytest tests/contracts/test_openapi_runtime_alignment.py -q` -> `1 passed`.

Smoke de endpoints (runtime real):
- Ejecucion automatica contra `app.url_map` (metodos GET/POST/PUT/PATCH/DELETE, excluyendo static/HEAD/OPTIONS).
- Cobertura: `118` reglas, `119` requests.
- Resultado final: `2xx=41`, `4xx=78`, `5xx/exceptions=0`.
- Evidencia: `artifacts/api_smoke/endpoint_smoke_report.json`.

Fix aplicado durante la validacion:
- Endpoint afectado: `POST /api/v2/questionnaires/admin/bootstrap` (fallo de idempotencia en reejecucion).
- Archivo: `api/services/questionnaire_v2_loader_service.py`.
- Correcciones:
  - upsert de `ModelArtifactRegistry` para evitar duplicate key en `(model_version_id, artifact_kind)`.
  - reemplazo de activaciones previas por `(domain, mode_key, role)` antes de crear la activa para evitar colision unique en `model_mode_domain_activation`.
- Resultado: bootstrap v2 vuelve a responder `201` en reintentos.

Validacion regresion asociada:
- `pytest tests/contracts/test_openapi_runtime_alignment.py tests/test_docs_metrics.py tests/api/test_questionnaire_v2_api.py tests/test_problem_reports.py -q` -> `21 passed`.
- `/openapi.yaml` y `/docs` operativos, consumiendo `docs/openapi.yaml`.

## Actualizacion (2026-04-18) - hardening de examples en requestBody OpenAPI
Objetivo ejecutado:
- Eliminar por completo en Swagger UI los request body con render por defecto tipo `additionalProp1` y reemplazarlos por payloads reales del contrato.

Cambios realizados en `docs/openapi.yaml`:
- Se actualizaron 22 operaciones con `requestBody` de runtime v1 y v2.
- Para endpoints que no consumen body en runtime, se retiro `requestBody`:
  - `POST /api/v1/questionnaire-runtime/evaluations/{evaluation_id}/heartbeat`
  - `PATCH /api/v1/questionnaire-runtime/notifications/{notification_id}/read`
  - `POST /api/v2/questionnaires/admin/bootstrap`
  - `POST /api/v2/questionnaires/history/{session_id}/pdf/generate`
- Para endpoints con body real, se definieron `properties`, `required` y `example` exactos segun schemas backend:
  - runtime v1 admin/evaluations/professional access/tag.
  - v2 sessions/answers/submit, history tags/share y reports jobs.

Verificacion:
- Auditoria automatica sobre request bodies: `problem_request_bodies=0` (sin cuerpos genericos sin ejemplo).
- Parseo YAML: `openapi_yaml_valid`.
- Tests:
  - `pytest tests/contracts/test_openapi_runtime_alignment.py tests/test_docs_metrics.py -q` -> `5 passed`.

Swagger/OpenAPI:
- Se mantiene fuente unica activa `docs/openapi.yaml`.
- `/openapi.yaml` y `/docs` siguen alineados con esa spec.

## Actualizacion (2026-04-18) - respuesta endpoint-por-endpoint y descripciones profesionales
Objetivo ejecutado:
- Resolver de forma completa la documentacion de respuestas en Swagger para evitar placeholders genericos y dejar ejemplos operativos por endpoint.

Acciones aplicadas en `docs/openapi.yaml`:
- Inputs:
  - se quitaron examples de request body en operaciones con body no obligatorio (`required: false`).
  - se garantizaron examples en todos los request body obligatorios (`required: true`).
- Outputs:
  - se agregaron examples concretos en todas las respuestas que no tenian example (75 respuestas cubiertas en esta pasada).
  - cobertura final auditada: `responses_without_example=0`.
  - no quedan respuestas que Swagger renderice con body por defecto tipo `additionalProp1`.
- Ajuste de exactitud de formato:
  - `GET /api/v2/questionnaires/history/{session_id}/pdf/download` (200) documentado como `application/pdf` binario.

Enriquecimiento profesional de descripciones:
- Se agrego seccion adicional por operacion con:
  - punto de control contractual (metodo+ruta),
  - seguridad y roles operativos,
  - respuestas HTTP auditadas,
  - comportamiento condicional por codigo de respuesta,
  - trazabilidad recomendada para auditoria.

Validacion:
- Parseo YAML: `openapi_yaml_valid`.
- Auditorias OpenAPI:
  - `responses_without_example=0`
  - `required_requestbody_without_example=0`
  - `optional_requestbody_with_example=0`
- Tests:
  - `pytest tests/contracts/test_openapi_runtime_alignment.py tests/test_docs_metrics.py tests/api/test_questionnaire_v2_api.py tests/test_problem_reports.py -q` -> `21 passed`.

Swagger/OpenAPI:
- Fuente activa unica confirmada: `docs/openapi.yaml`.
- `/openapi.yaml` y `/docs` continúan consistentes con esa spec.
