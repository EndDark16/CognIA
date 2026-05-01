# HANDOFF

## Resumen ejecutivo
Este proyecto es una tesis de ingenierÃ­a aplicada en salud mental infantil. El objetivo es sostener un sistema de alerta temprana para niÃ±os de 6 a 11 aÃ±os, con salida por 5 dominios:

- ADHD
- Conduct
- Elimination
- Anxiety
- Depression

El enfoque es conservador y metodolÃ³gicamente estricto:
- HBN es la base empÃ­rica.
- DSM-5 es el marco formal.
- El sistema tiene una capa interna diagnÃ³stica exacta y una capa externa por dominios.
- El entorno es simulado.
- No debe presentarse como diagnÃ³stico clÃ­nico definitivo.

## Estado actual por dominio
- ADHD: sÃ³lido.
- Anxiety: sÃ³lido.
- Conduct: sÃ³lido.
- Depression: sÃ³lido.
- Elimination: el dominio mÃ¡s difÃ­cil; sigue siendo el foco principal de mejora y validaciÃ³n estricta.

## Arquitectura / piezas visibles
Lo visible en el repositorio sugiere una plataforma con:
- modelos ML, principalmente Random Forest
- runtime de inferencia
- API/backend
- cuestionario real
- outputs para cuidador y psicÃ³logo

Los outputs deben sostener, como mÃ­nimo:
- riesgo
- confianza
- incertidumbre
- caveats

## Riesgos abiertos
- Elimination sigue siendo el dominio mÃ¡s frÃ¡gil.
- Existe riesgo de sobreprometer el alcance del sistema; debe mantenerse como screening/apoyo, no como diagnÃ³stico automÃ¡tico.
- Cualquier cambio de contrato entre modelo, runtime y cuestionario puede romper consistencia si no se valida.
- Si algo no estÃ¡ confirmado en el repo, no debe asumirse: marcarlo como `por confirmar`.

## Decisiones metodolÃ³gicas ya tomadas
- No vender el sistema como diagnÃ³stico clÃ­nico definitivo.
- Priorizar robustez, honestidad y trazabilidad.
- Evitar leakage, shortcuts y equivalencias dÃ©biles entre fuentes.
- Mantener caveats explÃ­citos en outputs y documentaciÃ³n.
- No romper artefactos histÃ³ricos o contratos sin migraciÃ³n clara.

## Pendientes inmediatos
- Confirmar el artefacto de inferencia que estÃ¡ promovido como referencia operativa.
- Revisar la lÃ­nea de Elimination antes de introducir mÃ¡s cambios de contrato u output.
- Verificar la alineaciÃ³n entre cuestionario, runtime y API.
- Confirmar quÃ© artefactos estÃ¡n congelados y cuÃ¡les siguen experimentales.

## QuÃ© revisar primero al retomar trabajo
1. `README.md`
2. `AGENTS_CONTEXT.md`
3. `docs/openapi.yaml`
4. `docs/OPENAPI_GUIDE.md`
5. Estado de `artifacts/inference_v4/` si aplica; si no estÃ¡ confirmado, tratarlo como `por confirmar`
6. Ãšltimos reportes y artefactos de Elimination

## Por confirmar
- VersiÃ³n exacta congelada del runtime final.
- Lista completa de artefactos definitivos vs experimentales.
- Cualquier contrato o versiÃ³n posterior no reflejada en `README.md`.

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

## Actualizacion (2026-04-17) - Descripciones Swagger en espanol por endpoint
Objetivo ejecutado:
- Se completo la documentacion de descripciones en espanol para todos los endpoints de `docs/openapi.yaml`.

Resultado de cobertura:
- Total de operaciones OpenAPI: `115`
- Operaciones con `description` en espanol: `115`
- Omisiones: `0`

Estandar aplicado por endpoint:
- objetivo funcional
- ruta/metodo
- seguridad declarada
- parametros de entrada
- body request si aplica
- respuestas de exito/error documentadas

Verificacion:
- Parseo YAML/OpenAPI correcto.
- `pytest tests/contracts/test_openapi_runtime_alignment.py -q` => `1 passed`.

Alcance:
- Cambio exclusivamente documental sobre contrato OpenAPI (`docs/openapi.yaml`).

## Actualizacion de sesion (2026-04-21) - hybrid_conduct_honest_retrain_v1 + freeze_v2
- Se ejecuto auditoria y retraining focal sobre los 4 slots activos de Conduct con metricas perfectas/sospechosas (`caregiver_2_3`, `caregiver_full`, `psychologist_2_3`, `psychologist_full`).
- Linea creada: `data/hybrid_conduct_honest_retrain_v1/` y `artifacts/hybrid_conduct_honest_retrain_v1/`.
- Script ejecutado: `scripts/run_hybrid_conduct_honest_retrain_v1.py`.
- Manifiesto: `artifacts/hybrid_conduct_honest_retrain_v1/hybrid_conduct_honest_retrain_v1_manifest.json`.

Auditoria causal (Conduct):
- No se detectaron duplicados exactos ni overlap de vectores entre train/val/holdout.
- No se detectaron features de leakage explicito (`target_*`/`*_threshold_met`) ni scores externos prohibidos en los 4 modelos auditados.
- Se confirmo patron de facilidad estructural: `conduct_impairment_global >= 2` logra BA holdout casi perfecta (inflacion de facilidad de dataset).

Decision de reemplazo:
- 4/4 modelos perfectos/sospechosos fueron reemplazados por variantes honestas `engineered_compact_no_shortcuts_v1`.
- Todos los reemplazos quedaron con headline metrics <= 0.98 en holdout para esos slots.
- Modelos previos quedaron demovidos en `data/hybrid_conduct_honest_retrain_v1/inventory/conduct_models_demoted.csv` con motivo de easy-dataset inflation.

Nuevas fuentes de verdad operativas:
- `data/hybrid_operational_freeze_v2/tables/hybrid_operational_final_champions.csv`
- `data/hybrid_active_modes_freeze_v2/tables/hybrid_active_models_30_modes.csv`
- `data/hybrid_active_modes_freeze_v2/tables/hybrid_active_modes_summary.csv`
- `data/hybrid_active_modes_freeze_v2/tables/hybrid_questionnaire_inputs_master.csv`

Cambios de integracion runtime:
- `api/services/questionnaire_v2_loader_service.py` actualizado para usar defaults `*_freeze_v2`.
- `v1` queda preservado como historico (no se sobreescribio).

Caveat de alcance:
- Esta intervencion fue focal a los casos perfectos/sospechosos de Conduct; existen otros pares de dominios distintos con metricas altas en indicadores secundarios que no fueron reentrenados en esta ventana.
- Claim permitido sin cambios: evidencia para screening/apoyo profesional en entorno simulado, no diagnostico automatico.

## Actualizacion de sesion (2026-04-21) - hybrid_secondary_honest_retrain_v1 + freeze_v3 (no-promote)
- Se ejecuto auditoria secundaria sobre la linea operativa post-Conduct para cubrir:
  - slots con metricas secundarias >0.98
  - slots con overfit persistente
- Linea creada: `data/hybrid_secondary_honest_retrain_v1/`.
- Script ejecutado: `scripts/run_hybrid_secondary_honest_retrain_v1.py`.
- Manifest: `artifacts/hybrid_secondary_honest_retrain_v1/hybrid_secondary_honest_retrain_v1_manifest.json`.

Prioridad atendida:
- `depression/caregiver_1_3`
- `depression/psychologist_1_3`
- Caso adicional por shortcut dominance:
  - `anxiety/psychologist_1_3`

Resultado de seleccion:
- `PROMOTE_NOW=0`
- `HOLD_FOR_LIMITATION=3`
- No hubo reemplazos promocionables en las nuevas lineas:
  - `artifacts/hybrid_operational_freeze_v3/hybrid_operational_freeze_v3_manifest.json` => `replaced_pairs=0`
  - `artifacts/hybrid_active_modes_freeze_v3/hybrid_active_modes_freeze_v3_manifest.json` => `replaced_pairs=0`

Implicacion operativa:
- Se versionaron `data/hybrid_operational_freeze_v3/` y `data/hybrid_active_modes_freeze_v3/` como evidencia de auditoria no-promocional.
- La fuente operativa efectiva se mantiene en `*_freeze_v2` (sin cambios de champions activos).

Hallazgos clave:
- No se observaron duplicados exactos globales en dataset auditado (`validation/duplicate_audit_global.csv`).
- Persisten metricas secundarias altas (>0.98) en varios slots de Anxiety/Elimination.
- `anxiety/psychologist_1_3` mantiene seÃ±al de shortcut dominance (feature agregada dominante), pero la mejor variante reentrenada no pasa gate secundario para promocion.
- `depression` short modes muestran reduccion de overfit gap, pero la calidad final sigue `malo`; no se rescatan para promocion honesta.

Claim permitido:
- Sin cambios: screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-21) - auth_mfa_recovery_flow_completion_v1
- Login `POST /api/auth/login` actualizado para aceptar credenciales por `identifier` (username o email), manteniendo compatibilidad con `username` y `email` legacy.
- Flujo de recovery codes MFA completado con endpoints nuevos:
  - `GET /api/mfa/recovery-codes/status`
  - `POST /api/mfa/recovery-codes/regenerate`
- `POST /api/auth/login/mfa` y `POST /api/mfa/disable` mantienen soporte de `recovery_code` de un solo uso.
- Regeneracion de recovery codes requiere verificacion fuerte (`password` + `code` TOTP o `recovery_code`).
- `docs/openapi.yaml` actualizado con:
  - contrato de login por username/email,
  - paths/schemas de recovery status/regenerate,
  - ejemplos de request/response.
- Documentacion de versionado endpoint-por-endpoint agregada en:
  - `docs/auth_mfa_recovery_flow_and_endpoint_versioning_20260421.md`
- Validacion ejecutada (focal):
  - `pytest tests/test_auth.py tests/contracts/test_openapi_runtime_alignment.py -q` => `21 passed`
  - `pytest tests/api/test_questionnaire_v2_api.py tests/api/test_questionnaire_runtime_api.py tests/services/test_questionnaire_v2_loader.py tests/contracts/test_hybrid_classification_policy_v1.py -q` => `15 passed`

## Actualizacion de sesion (2026-04-22) - hybrid_final_honest_improvement_v1 + freeze_v4
- Se ejecuto campana final de mejora honesta sobre la linea operativa `freeze_v2`, con foco en `full` y `2_3` para `anxiety`, `depression`, `elimination`.
- Linea creada: `data/hybrid_final_honest_improvement_v1/`.
- Script ejecutado: `scripts/run_hybrid_final_honest_improvement_v1.py`.
- Manifest: `artifacts/hybrid_final_honest_improvement_v1/hybrid_final_honest_improvement_v1_manifest.json`.

Cobertura de auditoria:
- Slots foco revisados: `12`.
- Deep retrain ejecutado en `12` slots (todos los `full/2_3` de `anxiety`, `depression`, `elimination`).

Resultado de seleccion:
- `PROMOTE_NOW=9`
- `HOLD_FOR_LIMITATION=3`
- Promovidos:
  - `anxiety/caregiver_2_3`
  - `anxiety/caregiver_full`
  - `anxiety/psychologist_2_3`
  - `anxiety/psychologist_full`
  - `depression/psychologist_2_3`
  - `elimination/caregiver_2_3`
  - `elimination/caregiver_full`
  - `elimination/psychologist_2_3`
  - `elimination/psychologist_full`
- No promocionados:
  - `depression/caregiver_2_3`
  - `depression/caregiver_full`
  - `depression/psychologist_full`
- Cambio destacado:
  - `depression/psychologist_2_3`:
    - old: `depression__psychologist_2_3__rebuild_v2__rf__full_eligible`
    - new: `depression__psychologist_2_3__final_honest_improvement_v1__rf__compact_subset`
    - mejora material: `BA +0.0351`, `F1 +0.0188`, `PR-AUC +0.0345`, `Brier -0.0050`
    - clase en champions v4: `PRIMARY_WITH_CAVEAT` (antes `HOLD_FOR_LIMITATION`)

Techo practico/caveats:
- En `anxiety` y `elimination` (modos `full` y `2_3`) persisten metricas secundarias >0.98; aun con mejora de BA/recall, se clasifican como `PRIMARY_WITH_CAVEAT` (no `ROBUST_PRIMARY`) por anomalia secundaria no resuelta.

Nuevas lineas operativas:
- `data/hybrid_operational_freeze_v4/` + `artifacts/hybrid_operational_freeze_v4/`
- `data/hybrid_active_modes_freeze_v4/` + `artifacts/hybrid_active_modes_freeze_v4/`
- `replaced_pairs=9` en:
  - `artifacts/hybrid_operational_freeze_v4/hybrid_operational_freeze_v4_manifest.json`
  - `artifacts/hybrid_active_modes_freeze_v4/hybrid_active_modes_freeze_v4_manifest.json`

Integracion runtime:
- `api/services/questionnaire_v2_loader_service.py` actualizado para defaults `*_freeze_v4`.

Impacto en confianza:
- Se recalculo en los slots promovidos, manteniendo no-promovidos sin cambios.
- Aumento material:
  - `depression/psychologist_2_3`: `54.1 -> 74.3` (`limited -> moderate`), `ACTIVE_LIMITED_USE -> ACTIVE_MODERATE_CONFIDENCE`.
- Ajuste conservador (sin inflar robustez limpia) en slots promovidos con anomalia secundaria persistente:
  - Anxiety/Elimination promovidos pasan a banda `moderate` con `PRIMARY_WITH_CAVEAT`.

## Actualizacion de sesion (2026-04-22) - backend_documentation_gap_closure_v1
Resumen de trabajo:
- Se auditaron y documentaron puntos backend 9-25 en matriz versionada.
- Nuevo artefacto: `docs/backend_gap_matrix_20260422.md`.

Decisiones principales:
- Se mantiene claim permitido:
  - entorno simulado para screening/apoyo profesional,
  - no diagnostico clinico automatico.
- Se separo explicitamente lo verificable en backend de lo que depende de frontend/compliance/ops externa.

Punto 24 (endpoints solapados):
- Hallazgo: endpoints v1 legacy aun activos en codigo para compatibilidad.
  - `POST /api/v1/questionnaires/{template_id}/activate`
  - `POST /api/v1/questionnaires/active/clone`
- Accion documental:
  - en `docs/openapi.yaml` quedaron marcados como `deprecated: true`.
  - se agrego reemplazo recomendado:
    - `.../activate` -> `POST /api/admin/questionnaires/{template_id}/publish`
    - `.../active/clone` -> `POST /api/admin/questionnaires/{template_id}/clone`
- Se corrigio `docs/api_full_reference.md` (ya no afirma retiro; ahora indica compatibilidad legacy deprecada).
- `docs/questionnaire_api_contract.md` actualizado con seccion de migracion v1 -> v2/admin.

Documentacion enlazada:
- `README.md` actualizado con nota de migracion de endpoints y enlace a matriz de brechas.
- `docs/traceability_map.md` actualizado para incluir `docs/backend_gap_matrix_20260422.md`.

Por confirmar:
- no se encontro en el arbol versionado de esta rama un `.txt` de despliegue adjunto; estado queda `por confirmar` hasta contar con archivo versionado.

## Actualizacion de sesion (2026-04-22) - admin_auth_regression_fix_and_full_test_pass_v1
Incidente en validacion completa:
- La corrida completa `pytest -q` detecto 3 fallas funcionales backend:
  - `POST /api/admin/roles` -> `405`
  - `POST /api/admin/impersonate/{user_id}` -> `404`
  - rate limit de `POST /api/auth/password/forgot` sin activar bajo config de test.

Correcciones aplicadas:
- `api/routes/admin.py`:
  - nuevo `POST /api/admin/roles` (creacion de rol)
  - nuevo `POST /api/admin/impersonate/{user_id}` (token temporal de impersonacion)
- `api/schemas/admin_schema.py`:
  - nuevo `RoleCreateSchema`
- `api/routes/auth.py`:
  - ajuste de prioridad en limite de `password/forgot` para respetar `PASSWORD_FORGOT_RATE_LIMIT` configurado.

Contrato OpenAPI alineado:
- `docs/openapi.yaml` ahora incluye:
  - `POST /api/admin/impersonate/{user_id}`
  - `POST` en `/api/admin/roles`
- Guardrail validado:
  - `pytest tests/contracts/test_openapi_runtime_alignment.py -q` => `1 passed`.

Estado de pruebas al cierre:
- `pytest -q` completo ejecutado sin saltos.
- Resultado: `139 passed, 3 skipped`.

## Actualizacion de sesion (2026-04-22) - deployment_playbook_ingest_v1
- Se incorporo el TXT de despliegue compartido por usuario:
  - `C:\Users\andre\Downloads\readme_deployment_summary.txt`.
- Documento nuevo versionado:
  - `docs/deployment_playbook_ingest_20260422.md`.

Hallazgos principales:
- La guia externa define una linea operativa completa (Ubuntu, Docker Compose, gateway, Cloudflare Tunnel/Access, runners, backups, hardening).
- En el backend repo actual se verifican `Dockerfile` y `docker-compose.yml`.
- Quedan `por confirmar` en esta rama artefactos mencionados por la guia pero no versionados aqui (como `.deploy/`, `deploy_wsgi.py`, `gateway/default.conf`, workflows de deploy indicados en el TXT).

Impacto documental:
- `docs/backend_gap_matrix_20260422.md` (punto 21) actualizado con referencia a evidencia externa.
- `README.md` y `docs/traceability_map.md` actualizados para enlazar la ingesta de despliegue.

Estado metodologico sin cambios:
- screening/apoyo profesional en entorno simulado.
- no diagnostico clinico automatico.

## Actualizacion de sesion (2026-04-22) - backend_release_versioning_framework_v1
Objetivo:
- establecer manejo de versiones backend profesional y repetible.

Implementacion:
- Se adopto esquema CalVer de backend: `YYYY.MM.DD-rN`.
- Version activa publicada en esta entrega: `2026.04.22-r1`.

Artefactos nuevos:
- `VERSION`
- `CHANGELOG.md`
- `docs/backend_versioning_policy.md`
- `docs/releases/backend_release_2026-04-22_r1.md`
- `artifacts/backend_release_registry/backend_release_2026-04-22_r1_manifest.json`

Valor operativo:
- cada release queda con trazabilidad tecnica+documental+validacion,
- facilita auditoria de cambios y handoff entre ramas/sesiones,
- evita depender solo de narrativa en chat o commits aislados.
- Refuerzo de gobernanza de release agregado:
  - `docs/backend_release_workflow.md`
  - `docs/backend_release_registry.csv`

## Actualizacion de sesion (2026-04-22) - sonarcloud_local_execution_and_security_hotspots_closure_v1
Alcance:
- Se incorporo ejecucion local de SonarCloud usando variables desde `.env`.
- Se versionaron artefactos de soporte:
  - `sonar-project.properties`
  - `scripts/run_sonar.ps1`
  - variables Sonar en `.env.example`.

Correcciones/hardening aplicados:
- `api/routes/auth.py`: regex de email endurecida.
- `api/services/questionnaire_runtime_service.py`: PRNG migrado a `secrets` para identificadores/PIN.
- `api/services/evaluation_service.py`: hash migrado de `md5` a `sha256` para `registration_number`.
- `api/routes/email.py`: handlers separados para unsubscribe `GET` y `POST`.
- `config/settings.py` + `.env.example`: `DEV_DEBUG=false` como default recomendado.

Estado reportado:
- Sonar Quality Gate en `PASSED`.
- Open issues en new code period: `0`.

## Actualizacion de sesion (2026-04-22) - hybrid_final_decisive_rescue_v5 + freeze_v5
Objetivo:
- cerrar incoherencias entre performance real, clase metodologica, confianza y activacion operativa en una sola pasada final.

Ejecucion:
- Script: `scripts/run_hybrid_final_decisive_rescue_v5.py`.
- Linea de campana: `data/hybrid_final_decisive_rescue_v5/`.
- Manifest: `artifacts/hybrid_final_decisive_rescue_v5/hybrid_final_decisive_rescue_v5_manifest.json`.

Resultado de seleccion:
- Slots foco auditados/reentrenados: `16`.
- Promociones: `1` (`depression/caregiver_2_3`).
- Resto de slots foco: `HOLD_FOR_LIMITATION` cuando no hubo mejora material defendible o persistio anomalia metodologica relevante.

Coherencia global de confianza (30 slots):
- Se recalculo `confidence_pct/confidence_band/final_operational_class` para los `30` slots.
- Regla dura aplicada: slots con anomalia secundaria no quedan en `ACTIVE_HIGH_CONFIDENCE`.
- Verificacion final: `0` slots `high` con anomalia secundaria.
- Distribucion activa v5:
  - `ACTIVE_MODERATE_CONFIDENCE=6`
  - `ACTIVE_LOW_CONFIDENCE=11`
  - `ACTIVE_LIMITED_USE=13`

Normalizacion metodologica:
- Nueva linea: `data/hybrid_classification_normalization_v2/`.
- Tabla: `tables/hybrid_operational_classification_normalized_v5.csv`.
- Violaciones de politica: `0` (`validation/hybrid_classification_policy_violations_v5.csv`).

Nuevas fuentes operativas:
- `data/hybrid_operational_freeze_v5/` + `artifacts/hybrid_operational_freeze_v5/`
- `data/hybrid_active_modes_freeze_v5/` + `artifacts/hybrid_active_modes_freeze_v5/`
- `replaced_pairs=1` en manifests de freeze v5.

Integracion runtime:
- `api/services/questionnaire_v2_loader_service.py` actualizado a defaults `*_freeze_v5`.

## Actualizacion de estado (2026-04-22) - hybrid_final_aggressive_rescue_v6 + freeze_v6
- Se ejecuto campana final agresiva con multipasadas internas A/B/C sobre 18 slots priorizados (Depression + anomalias secundarias + Conduct full opcional).
- Linea nueva:
  - `data/hybrid_final_aggressive_rescue_v6/`
  - `artifacts/hybrid_final_aggressive_rescue_v6/`
- Script principal:
  - `scripts/run_hybrid_final_aggressive_rescue_v6.py`
- Fuentes operativas versionadas:
  - `data/hybrid_operational_freeze_v6/`
  - `data/hybrid_active_modes_freeze_v6/`
- Manifests:
  - `artifacts/hybrid_final_aggressive_rescue_v6/hybrid_final_aggressive_rescue_v6_manifest.json`
  - `artifacts/hybrid_operational_freeze_v6/hybrid_operational_freeze_v6_manifest.json`
  - `artifacts/hybrid_active_modes_freeze_v6/hybrid_active_modes_freeze_v6_manifest.json`
- Resultado de seleccion:
  - `focus_slots=18`
  - `PROMOTE_NOW=2`
  - `HOLD_FOR_LIMITATION=16`
  - `policy_violations=0`
- Reemplazos promocionados:
  - `conduct/caregiver_full` -> `extra_trees + dsm5_core_plus_context`
  - `conduct/psychologist_full` -> `hgb + dsm5_core_plus_context`
- Auditorias generadas:
  - split/duplicates (`validation/split_registry.csv`, `validation/duplicate_audit_global.csv`)
  - trials por pasada (`trials/focus_pass_a_trials.csv`, `focus_pass_b_trials.csv`, `focus_pass_c_trials.csv`, `final_aggressive_retrain_trials.csv`)
  - evidencia global 30 slots (`validation/global_model_evidence_v6.csv`)
  - bootstrap/stability/ablation/stress (`bootstrap/global_bootstrap_v6.csv`, `stability/global_seed_stability_v6.csv`, `ablation/global_ablation_v6.csv`, `stress/global_stress_v6.csv`)
  - normalizacion/policy (`data/hybrid_classification_normalization_v2/tables/hybrid_operational_classification_normalized_v6.csv`, `validation/hybrid_classification_policy_violations_v6.csv`)
- Loader/backend:
  - `api/services/questionnaire_v2_loader_service.py` actualizado a defaults `*_freeze_v6`.
- Contrato funcional:
  - No hubo cambio de inputs funcionales expuestos ni outputs funcionales expuestos.
  - Se mantuvieron `domain/mode/role` y semantica de inferencia; cambios solo en entrenamiento interno/seleccion/calibracion/threshold/weighting.

## Actualizacion de estado (2026-04-24) - hybrid_v6_quick_champion_guard_hotfix_v1
- Objetivo:
  - corregir de inmediato champions activos v6 que violaban guardia dura (`recall|specificity|roc_auc|pr_auc > 0.98`).
- Script:
  - `scripts/run_hybrid_v6_quick_champion_guard_hotfix.py`
- Fuentes de verdad nuevas:
  - `data/hybrid_operational_freeze_v6_hotfix_v1/tables/hybrid_operational_final_champions.csv`
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_active_models_30_modes.csv`
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_active_modes_summary.csv`
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_questionnaire_inputs_master.csv`
- Evidencia:
  - `data/hybrid_v6_quick_champion_guard_hotfix_v1/tables/violating_slots_v6.csv`
  - `data/hybrid_v6_quick_champion_guard_hotfix_v1/tables/final_old_vs_new_comparison.csv`
  - `data/hybrid_v6_quick_champion_guard_hotfix_v1/tables/remaining_guard_violations_after_hotfix.csv`
  - `data/hybrid_classification_normalization_v2/validation/hybrid_classification_policy_violations_v6_hotfix_v1.csv`
- Resultado final:
  - `violating_slots_before=16`
  - `corrected_slots_total=16`
  - `remaining_guard_violations=0`
  - `policy_violations=0`
- Integracion loader/runtime:
  - defaults de `api/services/questionnaire_v2_loader_service.py` migrados a `*_freeze_v6_hotfix_v1`.


## Actualizacion de estado (2026-04-24) - cierre operativo guardia dura v6_hotfix_v1
- Se verifico estado real de violaciones en lineas `v6` y `v6_hotfix_v1` antes de cierre:
  - `v6`: `16` violadores.
  - `v6_hotfix_v1`: `0` violadores.
- Se confirma `v6_hotfix_v1` como fuente operativa efectiva de champions activos (no `v6`).
- Se alineo validacion contractual para evaluar la linea activa `v6_hotfix_v1`:
  - `scripts/validate_hybrid_classification_policy_v1.py`
  - `tests/contracts/test_hybrid_classification_policy_v1.py`
- Se mantiene framing metodologico:
  - screening/apoyo profesional en entorno simulado.
  - no diagnostico automatico.

## Actualizacion de estado (2026-04-24) - coherencia confidence/clase v6_hotfix_v1
- Auditoria inicial de linea activa real (segun loader v2):
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_active_models_30_modes.csv`
  - `data/hybrid_operational_freeze_v6_hotfix_v1/tables/hybrid_operational_final_champions.csv`
- Guardrails duros:
  - `0` champions activos con `recall|specificity|roc_auc|pr_auc > 0.98`.
- Incoherencias corregidas:
  - `12` filas `ACTIVE_MODERATE_CONFIDENCE` con `confidence_band=high`.
- Politica comunicacional aplicada:
  - `ACTIVE_MODERATE_CONFIDENCE -> confidence_band=moderate`.
  - `ACTIVE_LIMITED_USE -> confidence_band=limited`.
  - `ACTIVE_HIGH_CONFIDENCE -> confidence_band=high` solo sin caveat metodologico fuerte.
- No hubo reemplazo de champions ni reentrenamiento en esta ventana porque la hotfix real ya no tenia violadores.
- Se actualizaron `README.md`, `docs/traceability_map.md`, `docs/model_registry_and_inference.md` y `docs/hybrid_operational_classification_policy_v1.md` para alinear fuente activa y confianza.

## Actualizacion de sesion (2026-04-25) - development branch reconciliation ops v1
Objetivo:
- Auditar todas las ramas remotas del backend y sanear `development` en automatizacion CI/CD y operacion.

Resultado:
- Se auditaron ramas remotas contra `origin/development` con `git fetch --all --prune`.
- Reporte versionado: `docs/ops/development-branch-reconciliation-audit.md`.

Decisiones aplicadas:
- `.github/workflows/ci.yml` eliminado como CI legado duplicado.
- `.github/workflows/ci-backend.yml` queda como CI backend unico y autoritativo.
- `ci-backend.yml` suma Ruff F-check manteniendo compile/import sanity, `pytest -q` y docker build sanity.
- `.github/workflows/deploy-backend.yml` queda robustecido:
  - verifica `github.sha` contra `origin/development`,
  - reconstruye `backend`,
  - recrea `gateway` con `--force-recreate`,
  - mantiene `readyz` y rollback,
  - publica logs de `backend` y `gateway`.
- `docs/openapi.yaml` corregido para que tres operaciones admin cumplan secciones obligatorias y para normalizar estados residuales health/readiness/metrics a `x-contract-status=KEEP_ACTIVE`.
- Verificacion final local: `pytest -q` => `149 passed, 3 skipped`.

No aplicado:
- No se consolidaron ramas v6/v7 de modelado en esta ventana; requieren decision metodologica separada.
- No se agrego `.deploy/` porque no existe version auditada en ramas remotas.

Pendiente:
- Rehabilitar workflows en GitHub con una corrida controlada tras revisar el commit final.

## Actualizacion de estado (2026-04-26) - hybrid_structural_mode_rescue_v1
- Se ejecuto una intervencion focal estructural sobre la linea activa real `v6_hotfix_v1` en la rama `fix/structural-mode-model-rescue-v1`, sin commits directos sobre `development` ni `dev.enddark`.
- Lineas versionadas nuevas:
  - `data/hybrid_structural_mode_rescue_v1/`
  - `artifacts/hybrid_structural_mode_rescue_v1/`
  - `data/hybrid_active_modes_freeze_v8/`
  - `artifacts/hybrid_active_modes_freeze_v8/`
  - `data/hybrid_operational_freeze_v8/`
  - `artifacts/hybrid_operational_freeze_v8/`
- Script principal: `scripts/run_hybrid_structural_mode_rescue_v1.py`.
- Resultado de cierre: `blacklisted_active_initial=14`, `accepted_existing_fallbacks=0`, `structural_extra_rescue_initial=3`, `retrained_structural_replacements=17`, `blacklisted_active_final=0`, `structural_extra_rescue_final=0`, `single_feature_active_final=0`, `guardrail_violations_final=0`, `policy_violations_final=0`.
- Los 14 champions 1/3 y 2/3 prohibidos fueron removidos de la linea activa; ademas se rescataron 3 champions extra de una sola variable (`anxiety/psychologist_full` y los dos `elimination/*_full`). Elimination queda en subsets estructurales `structural_ranked` para sus 6 modos.
- `api/services/questionnaire_v2_loader_service.py` apunto en esa ventana a `hybrid_active_modes_freeze_v8` y `hybrid_operational_freeze_v8`; desde v9 la fuente activa vigente es `hybrid_active_modes_freeze_v9`/`hybrid_operational_freeze_v9`.
- Caveat metodologico vigente: persiste sensibilidad `drop_top1`/stress en Elimination y parte de Depression; la linea final queda sin champions de una sola feature y la evidencia sigue siendo para screening/apoyo profesional en entorno simulado, no diagnostico automatico.

## Actualizacion de estado (2026-04-26) - hybrid_elimination_structural_audit_rescue_v1
- Se ejecuto auditoria focal y reentrenamiento de los 6 slots Elimination sobre la linea activa `v8`.
- Script principal: `scripts/run_hybrid_elimination_structural_audit_rescue_v1.py`.
- Lineas versionadas nuevas:
  - `data/hybrid_elimination_structural_audit_rescue_v1/`
  - `artifacts/hybrid_elimination_structural_audit_rescue_v1/`
  - `data/hybrid_operational_freeze_v9/`
  - `artifacts/hybrid_operational_freeze_v9/`
  - `data/hybrid_active_modes_freeze_v9/`
  - `artifacts/hybrid_active_modes_freeze_v9/`
- Diagnostico de v8: los 6 slots Elimination colapsaban a la misma frontera HGB; auditoria reconstruida: `old_prediction_pairs_identical=15/15`.
- Correccion aplicada: reentrenamiento Elimination-only con features directas enuresis/encopresis por rol, exclusion de `eng_elimination_intensity`, seleccion guard-aware y regla anti-clonado.
- Resultado v9: `remaining_guardrail_violations=0`, `policy_violations=0`, `new_prediction_pairs_identical=0/15`.
- `api/services/questionnaire_v2_loader_service.py` apunta ahora por defecto a `hybrid_active_modes_freeze_v9` y `hybrid_operational_freeze_v9`.
- Tambien se corrigio `docs/openapi.yaml`: se elimino un bloque duplicado en `paths` que provocaba `duplicated mapping key`; el spec conserva `openapi: 3.0.3` y parsea sin claves duplicadas.
- Claim permitido sin cambios: evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.


## Actualizacion de estado (2026-04-26) - hybrid_final_model_structural_compliance_v1
- Se ejecuto pasada final focal sobre la linea activa real `v9` en la rama `fix/final-model-structural-compliance-v1`.
- Lineas versionadas nuevas:
  - `data/hybrid_final_model_structural_compliance_v1/`
  - `artifacts/hybrid_final_model_structural_compliance_v1/`
  - `data/hybrid_active_modes_freeze_v10/`
  - `artifacts/hybrid_active_modes_freeze_v10/`
  - `data/hybrid_operational_freeze_v10/`
  - `artifacts/hybrid_operational_freeze_v10/`
- Script principal: `scripts/run_hybrid_final_model_structural_compliance_v1.py`.
- Resultado: `target_slots_for_retrain=20`, `trials=640`, `selected_promotions=5`, `anti_clone_reverted_promotions=3`, `retained_after_retrain_attempt=15`, `remaining_guardrail_violations=0`, `policy_violations=0`.
- Promociones: `adhd/psychologist_1_3`, `anxiety/psychologist_1_3`, `depression/caregiver_full`, `depression/psychologist_1_3`, `elimination/psychologist_full`.
- La auditoria anti-clonado revirtio tres challengers Elimination que repetian la misma frontera practica y retuvo los champions v9 no clonados para `elimination/caregiver_2_3`, `elimination/psychologist_1_3` y `elimination/psychologist_2_3`.
- Se sincronizaron flags del cuestionario v16.4 para modos 1_3/2_3 desde inputs finales de champions, reutilizando preguntas full auditadas; `question_text_changes=0`, `questionnaire_mode_flag_changes=68` vs `origin/development`.
- Se reconstruyo `feature_list_pipe` para 5 champions heredados retenidos desde sus registros fuente, dejando `active_model_versions_without_feature_columns=0` en BD.
- Supabase/Postgres se sincronizo con `python scripts/bootstrap_questionnaire_backend_v2.py load-all`: `questions=146`, `active_model_activations=30`, `duplicate_active_domain_mode_rows=0`; evidencia en `data/hybrid_final_model_structural_compliance_v1/questionnaire_sync/supabase_sync_verification_v10.json`.
- `api/services/questionnaire_v2_loader_service.py` apunta ahora por defecto a `hybrid_active_modes_freeze_v10` y `hybrid_operational_freeze_v10`, y limpia activaciones antiguas por `domain/mode` para evitar convivencia de roles legacy `caregiver` con `guardian`.
- Claim permitido sin cambios: evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-27) - hybrid_rf_max_real_metrics_v1
- Se ejecuto campana RF-only sobre los 30 slots activos reales desde `hybrid_active_modes_freeze_v10` / `hybrid_operational_freeze_v10`, en rama `train/rf-max-real-metrics-v1`.
- Script principal: `scripts/run_hybrid_rf_max_real_metrics_v1.py`.
- Lineas versionadas nuevas:
  - `data/hybrid_rf_max_real_metrics_v1/`
  - `artifacts/hybrid_rf_max_real_metrics_v1/`
  - `data/hybrid_active_modes_freeze_v11/`
  - `artifacts/hybrid_active_modes_freeze_v11/`
  - `data/hybrid_operational_freeze_v11/`
  - `artifacts/hybrid_operational_freeze_v11/`
- Resultado: `active_rows=30`, `trials=2160`, `rf_only_ok=yes`, `remaining_guardrail_violations=0`, `policy_violations=0`, `feature_contract_mismatches=0`, `questionnaire_changed=no`, `elimination_identical_prediction_pairs=0`.
- La linea final queda RF-only para los 30 slots, manteniendo exactamente los `feature_list_pipe` de v10 por slot y sin cambios de preguntas/inputs funcionales/outputs funcionales.
- Resultado agregado vs v10: F1 medio estable (`+0.00006`), recall medio `+0.01053`, balanced accuracy media `+0.00357`, precision media `-0.00787`, Brier medio `+0.00483`.
- Hubo 13 regresiones de F1 frente a champions v10, documentadas como consecuencia honesta del mandato RF-only cuando el mejor RF valido no supero al champion anterior.
- Supabase/Postgres se sincronizo con la linea v11 y quedo evidencia en `data/hybrid_rf_max_real_metrics_v1/supabase_sync/supabase_sync_verification_v11.json`: `active_activations_db=30`, `active_model_versions_non_rf=0`, `missing_expected_models=0`, `mismatched_feature_columns=0`.
- `api/services/questionnaire_v2_loader_service.py` apunta ahora por defecto a `hybrid_active_modes_freeze_v11` y `hybrid_operational_freeze_v11`.
- Caveat metodologico vigente: evidencia para screening/apoyo profesional en entorno simulado, no diagnostico automatico; Elimination ya no presenta predicciones binarias identicas entre sus 6 slots, pero conserva alta correlacion en algunos pares full/2_3 y requiere caveat operativo.

## Actualizacion de estado (2026-04-27) - hybrid_final_rf_plus_maximize_metrics_v1
- Se ejecuto campana final RF-based sobre los 30 slots activos reales desde `hybrid_active_modes_freeze_v11` / `hybrid_operational_freeze_v11`, en rama `train/final-rf-plus-maximize-metrics-v1`.
- Script principal: `scripts/run_hybrid_final_rf_plus_maximize_metrics_v1.py`.
- Lineas versionadas nuevas:
  - `data/hybrid_final_rf_plus_maximize_metrics_v1/`
  - `artifacts/hybrid_final_rf_plus_maximize_metrics_v1/`
  - `data/hybrid_active_modes_freeze_v12/`
  - `artifacts/hybrid_active_modes_freeze_v12/`
  - `data/hybrid_operational_freeze_v12/`
  - `artifacts/hybrid_operational_freeze_v12/`
- La linea final mantiene RandomForestClassifier como base obligatoria para 30/30 champions; se permitieron calibracion/thresholding/resampling train-only y regularizacion alrededor de RF sin usar familias no-RF como champion.
- Resultado de campana: `trials=5400`, `rf_only_ok=yes`, `remaining_guardrail_violations=0`, `policy_violations=0`, `feature_contract_mismatches=0`, `questionnaire_changed=no`, `elimination_identical_prediction_pairs=0`.
- Delta agregado v12 vs v11: F1 medio `+0.003995`, recall medio `-0.005088`, precision media `+0.011399`, BA media `-0.000095`, Brier medio `-0.001543`.
- F1 mejoro o empato en `29/30` slots; la unica regresion fue `elimination/psychologist_full` (`-0.007003`) por seleccion anti-clonado metodologicamente mas conservadora.
- Supabase/Postgres se sincronizo con la linea v12 y quedo evidencia en `data/hybrid_final_rf_plus_maximize_metrics_v1/supabase_sync/supabase_sync_verification_v12.json`: `active_activations_db=30`, `active_model_versions_non_rf=0`, `missing_expected_models=0`, `mismatched_feature_columns=0`.
- `api/services/questionnaire_v2_loader_service.py` apunta ahora por defecto a `hybrid_active_modes_freeze_v12` y `hybrid_operational_freeze_v12`.

## Actualizacion de estado (2026-04-29) - hybrid_global_contract_compatible_rf_champion_selection_v13
- Se ejecuto correccion rapida de seleccion de champions RF contract-compatible, sin campana nueva de entrenamiento.
- Rama de trabajo: `fix/global-compatible-rf-champion-selection-v13`.
- Script principal: `scripts/build_hybrid_global_contract_compatible_rf_champion_selection_v13.py`.
- Linea versionada creada:
  - `data/hybrid_global_contract_compatible_rf_champion_selection_v13/`
  - `artifacts/hybrid_global_contract_compatible_rf_champion_selection_v13/`
  - `data/hybrid_active_modes_freeze_v13/`
  - `artifacts/hybrid_active_modes_freeze_v13/`
  - `data/hybrid_operational_freeze_v13/`
  - `artifacts/hybrid_operational_freeze_v13/`
- Alcance: seleccion de champions activos entre RF v12, RF v11 y candidatos historicos solo si cumplen contrato actual exacto de `feature_list_pipe`, orden de columnas, threshold valido, metadata activable, metricas comparables y gate duro.
- Resultado: `active_rows=30`, `rf_rows=30`, `selected_from_v11=17`, `selected_from_v12=13`, `guardrail_violations=0`, `policy_violations=0`, `near_clone_proxy_pairs=0`.
- No se modificaron preguntas, cuestionario, inputs funcionales, outputs funcionales ni semantica de dominio/modo/rol.
- `api/services/questionnaire_v2_loader_service.py` apunta ahora por defecto a `hybrid_active_modes_freeze_v13` y `hybrid_operational_freeze_v13`.
- Claim permitido sin cambios: evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.
- Supabase/Postgres sincronizado tras `load-all`: `active_activations_db=30`, `active_model_versions_non_rf=0`, `missing_expected_models=0`, `mismatched_feature_columns=0`; evidencia en `data/hybrid_global_contract_compatible_rf_champion_selection_v13/supabase_sync/supabase_sync_verification_v13.json`.

## Actualizacion de estado (2026-05-01) - hybrid_v13_real_prediction_anti_clone_audit
- Objetivo ejecutado: auditoria anti-clone fuerte y rapida sobre linea activa `v13`, con recomputacion real de probabilidades/predicciones en holdout para `30/30` champions.
- Rama: `audit/v13-real-prediction-anti-clone`.
- Script nuevo:
  - `scripts/run_hybrid_v13_real_prediction_anti_clone_audit.py`
- Fuente versionada de salida:
  - `data/hybrid_v13_real_prediction_anti_clone_audit/`
- Resultado tecnico principal:
  - `prediction_recomputed_slots=30/30`
  - `artifacts_available_slots=30/30`
  - `metrics_match_registered=yes` en `30/30` slots (`tolerance=1e-6`)
  - `artifact_duplicate_hash_count=0`
  - `all_domains_real_clone_count=4`
  - `elimination_real_clone_count=4`
  - `all_domains_near_clone_warning_count=23`
  - `final_audit_status=fail`
- Pairs Elimination con `real_clone_flag=yes`:
  - `caregiver_full` vs `psychologist_1_3`
  - `caregiver_full` vs `psychologist_2_3`
  - `caregiver_full` vs `psychologist_full` (prediccion binaria identica)
  - `psychologist_1_3` vs `psychologist_2_3`
- Inventario clave generado:
  - `tables/v13_recomputed_champion_metrics.csv`
  - `tables/v13_registered_vs_recomputed_metrics.csv`
  - `tables/v13_pairwise_prediction_similarity_all_domains.csv`
  - `tables/v13_elimination_real_prediction_similarity.csv`
  - `validation/v13_real_prediction_anti_clone_validator.csv`
  - `validation/v13_recomputed_metrics_match_validator.csv`
  - `validation/v13_artifact_availability_validator.csv`
  - `validation/v13_elimination_clone_risk_validator.csv`
  - `reports/v13_real_prediction_anti_clone_report.md`
- Notas operativas:
  - No hubo reentrenamiento ni cambios de champions en esta ventana.
  - No hubo cambios en inputs/outputs funcionales ni en preguntas del cuestionario.
  - Estado de cierre de auditoria: bloquear promocion afirmativa de “sin clonado” hasta resolver/aceptar explicitamente los 4 pares marcados por criterio estricto.

## Actualizacion de estado (2026-05-01) - hybrid_elimination_v14_real_anti_clone_rescue
- Objetivo ejecutado: correccion focal del clonado conductual real en Elimination detectado en v13, sin campana general y sin tocar los otros 24 champions.
- Rama: `fix/elimination-v14-real-anti-clone-rescue`.
- Script:
  - `scripts/run_hybrid_elimination_v14_real_anti_clone_rescue.py`
- Salidas versionadas:
  - `data/hybrid_elimination_v14_real_anti_clone_rescue/`
  - `artifacts/hybrid_elimination_v14_real_anti_clone_rescue/`
  - `data/hybrid_active_modes_freeze_v14/`
  - `artifacts/hybrid_active_modes_freeze_v14/`
  - `data/hybrid_operational_freeze_v14/`
  - `artifacts/hybrid_operational_freeze_v14/`
- Resultado tecnico:
  - `prediction_recomputed_slots=30/30`
  - `elimination_real_clone_count=0`
  - `all_domains_real_clone_count=0`
  - `artifact_duplicate_hash_count=0`
  - `guardrail_violations=0`
  - `final_audit_status=pass_with_warnings` (warnings near-clone sin clonado real).
- Restricciones cumplidas:
  - 6 slots Elimination RF-based corregidos.
  - 24 no-Elimination sin cambios (`validation/v14_non_elimination_unchanged_validator.csv`).
  - Contrato exacto de features/inputs/outputs 30/30 (`validation/v14_contract_compatibility_validator.csv`).
  - Sin cambios de preguntas/cuestionario.
- Loader/runtime:
  - `api/services/questionnaire_v2_loader_service.py` actualizado a defaults `*_freeze_v14`.


## Actualizacion 2026-05-01 - v15 caregiver_full metric rescue
- Linea nueva: `hybrid_elimination_v15_caregiver_full_metric_rescue`.
- Freeze activo generado: `hybrid_active_modes_freeze_v15` + `hybrid_operational_freeze_v15`.
- Mejora focal lograda en `elimination/caregiver_full` sin clonado real:
  - `F1 0.712871 -> 0.820513`, `recall 0.692308 -> 0.923077`, `BA 0.830967 -> 0.941679`.
- Auditoria real v15: `prediction_recomputed=30/30`, `elimination_real_clone_count=0`, `all_domains_real_clone_count=0`, `guardrail_violations=0`, `final_audit_status=pass_with_warnings`.
- Cambios runtime/DB:
  - Loader por defecto movido a `*_freeze_v15`.
  - Fix aplicado en loader para serializacion JSON-safe (`NaN/inf -> null`) en `model_metrics_snapshot.metrics_json`.
  - `python scripts/bootstrap_questionnaire_backend_v2.py load-all` exitoso contra Supabase/Postgres.
- Evidencia principal:
  - `data/hybrid_elimination_v15_caregiver_full_metric_rescue/reports/v15_elimination_caregiver_full_metric_rescue_report.md`
  - `data/hybrid_elimination_v15_caregiver_full_metric_rescue/validation/v15_real_prediction_anti_clone_validator.csv`
  - `data/hybrid_elimination_v15_caregiver_full_metric_rescue/validation/v15_supabase_sync_verification.json`
## Actualizacion de estado (2026-05-01) - hybrid_final_clean_champion_resolution_v16
- Objetivo ejecutado: cierre final limpio de la linea activa para eliminar `pass_with_warnings` y pendientes ambiguos.
- Script:
  - `scripts/run_hybrid_final_clean_champion_resolution_v16.py`
- Salidas versionadas:
  - `data/hybrid_final_clean_champion_resolution_v16/`
  - `data/hybrid_active_modes_freeze_v16/`
  - `artifacts/hybrid_active_modes_freeze_v16/`
  - `data/hybrid_operational_freeze_v16/`
  - `artifacts/hybrid_operational_freeze_v16/`
- Resultado tecnico:
  - `final_audit_status=pass`
  - `prediction_recomputed_slots=30/30`
  - `metrics_match_registered=yes 30/30`
  - `all_domains_real_clone_count=0`
  - `elimination_real_clone_count=0`
  - `unresolved_near_clone_warning_count=0`
  - `guardrail_violations=0`
  - `artifact_duplicate_hash_count=0`
- Semantica lineage/DB:
  - Lineage mixto de champions RF historicos se mantiene por diseno (`mixed_lineage_expected=yes`).
  - Validacion DB se enfoca en integridad de set activo (`db_active_set_valid`) y no en exigir lineage unico.
- Loader/runtime:
  - Defaults movidos a `*_freeze_v16`.
