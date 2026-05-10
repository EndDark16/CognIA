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

## Actualizacion de sesion (2026-05-10) - A2 capacity/reliability optimization
- Se completo una intervencion interna A2 orientada a subir capacidad real en homelab sin romper contratos API existentes.
- Rama aplicada: `perf/a2-capacity-reliability-optimization`.
- Mejoras tecnicas integradas:
  - cache backend extensible: memory default + Redis opcional con fallback.
  - cache de `/api/auth/me` con TTL corto e invalidaciones consistentes.
  - cache multi-capa de `GET /api/v2/questionnaires/active` (version/activacion/question-bank/payload).
  - invalidaciones centralizadas en sync/bootstrap de cuestionario/modelos.
  - optimizacion de metricas (lock reduction + sample size configurable + exclusion opcional de detalle en health/ready).
  - script operativo `scripts/warmup_backend.py` para precalentar rutas no destructivas.
  - suite k6 A2 agregada para separar infraestructura vs flujo de usuario:
    - `k6_infra_smoke.js`
    - `k6_auth_read.js`
    - `k6_qv2_active_read.js`
    - `k6_user_journey_read.js`
    - `k6_capacity_ladder.js`
    - `k6_constant_rps.js`
  - cache LRU para `feature contract` y clave de cifrado de campos.
  - `create_session` optimizado con insercion batch de session items.
- Validacion local A2:
  - `ruff check --select F api tests`: OK
  - `python -m compileall -q api app config core scripts run.py`: OK
  - `python -c "from api.app import create_app; app = create_app(); print(app.name)"`: OK
  - `pytest -q`: `188 passed, 3 skipped`
  - `k6 inspect` de suite previa y A2: OK
- Restricciones respetadas:
  - frontend sin cambios,
  - contratos API existentes sin ruptura,
  - logica clinica/metodologica sin alteraciones.
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

## Actualizacion de sesion (2026-05-10) - perf_safe_backend_optimization_audit_v1
Alcance:
- Auditoria backend de performance/estabilidad/seguridad operativa en rama:
  - `perf/safe-backend-optimization-audit`.
- Se preservo worktree sucio preexistente sin limpieza/integracion.
- Archivos protegidos sin tocar:
  - `scripts/hardening_second_pass.py`
  - `scripts/rebuild_dsm5_exact_datasets.py`
  - `scripts/run_pipeline.py`
  - `scripts/seed_users.py`
  - `tests/test_health.py`

Evidencia de estado inicial:
- `reports/audit/backend_perf_stability_security_audit_2026-05-10.md`
  - incluye `git status --short` y resumen de `git diff` de los archivos protegidos.

Cambios seguros aplicados:
- Cache de modelo en predict:
  - `core/models/predictor.py` (`lru_cache` para evitar `joblib.load` por request).
- Reduccion de queries repetidas en v2:
  - `api/services/questionnaire_v2_service.py`
    - `save_answers` con prefetch de preguntas/respuestas/repeat mapping,
    - `list_history` sin N+1 para summary,
    - `_recompute_progress` con agregacion unica.
- Configuracion operativa tunable por entorno:
  - `config/settings.py`: `DB_POOL_*` + `RATELIMIT_STORAGE_URI`.
  - `docker/entrypoint.sh`: soporte opcional `GUNICORN_TIMEOUT`, `GUNICORN_KEEPALIVE`, `GUNICORN_MAX_REQUESTS`, `GUNICORN_MAX_REQUESTS_JITTER`.
  - `.env.example` y `README.md` actualizados.

Suite formal k6 agregada:
- `scripts/load/helpers.js`
- `scripts/load/k6_smoke.js`
- `scripts/load/k6_baseline.js`
- `scripts/load/k6_load.js`
- `scripts/load/k6_stress.js`
- `scripts/load/k6_spike.js`
- `scripts/load/k6_soak.js`
- `scripts/load/k6_questionnaire_v2_flow.js`
- `scripts/load/README.md`
- `scripts/k6_smoke.js` mantenido compatible y alineado.

Documentacion/evidencia de carga:
- `docs/load_testing.md`
- `reports/load_tests/README.md`
- `reports/load_tests/summary_template.md`
- `reports/load_tests/2026-05-10_preopt_production_smoke_summary.md`

Baseline probe de despliegue (ligero, no stress):
- `GET /healthz` y `GET /readyz` en root => `200`.
- `GET /api/healthz` y `GET /api/readyz` => `404` en despliegue observado.
- endpoints autenticados sin token => `401` esperado.
- caveat TLS en esta estacion: probe ejecutado con verificacion TLS desactivada para reachability.

Validacion local en esta ventana:
- `ruff check --select F api tests` => `passed`.
- `python -m compileall -q api app config core scripts run.py` => `passed`.
- `python -c "from api.app import create_app; app = create_app(); print(app.name)"` => `api.app`.
- `pytest -q` => `148 passed, 3 skipped`.
- `docker build` no ejecutable por daemon local no disponible.

Pendiente operativo:
- carga/estres real contra `https://www.cognia.lat/api` queda `por confirmar` hasta contar con credenciales de prueba dedicadas y ventana controlada.

Actualizacion operativa (2026-05-10) - ejecucion real en produccion:
- Flujo de ramas completado:
  - `perf/safe-backend-optimization-audit` -> `dev.enddark` -> `development` -> `main`.
- PRs:
  - `#133` merged (perf -> dev.enddark)
  - `#134` merged (dev.enddark -> development)
  - `#135` merged (development -> main)
- SHA en `main`: `193de2ab1b71a79f2d60b9e3b131852220ca178c`.
- Workflows en ese SHA:
  - `CI Backend`: success
  - `Deploy Backend (Best Effort)`: success
- Patron health/readiness confirmado:
  - root (`/healthz`, `/readyz`) responde `200`
  - bajo `/api` para health/readiness responde `404`
- Configuracion efectiva usada en k6:
  - `BASE_URL=https://www.cognia.lat`
  - `API_PREFIX=/api`
- Usuario de prueba sintetico creado con prefijo `perf_loadtest_` (sin uso de usuarios reales).
- Escenarios ejecutados:
  - `smoke`: ejecutado, disponibilidad mantenida; `http_req_failed=2.74%`; p95 global ~`6377 ms`.
  - `baseline`: ejecutado; `http_req_failed=32.70%`; p95 global ~`7615 ms`; degradacion severa sostenida.
- Criterio de parada obligatorio activado en baseline:
  - `error rate > 5%` por mas de 60s.
- Escenarios no ejecutados por seguridad operativa:
  - `load`, `stress`, `spike`, `soak`, `questionnaire_v2_flow`.
- Reportes versionables agregados:
  - `reports/load_tests/2026-05-10_prod_smoke_summary.md`
  - `reports/load_tests/2026-05-10_prod_baseline_summary.md`
  - `reports/load_tests/2026-05-10_prod_load_summary.md`
  - `reports/load_tests/2026-05-10_prod_stress_summary.md`
  - `reports/load_tests/2026-05-10_backend_perf_final_report.md`

## Actualizacion de sesion (2026-05-10) - A1 backend internal optimization
- Se completo una intervencion interna A1 enfocada en performance, observabilidad y estabilidad operativa sin romper contratos API publicos.
- Cambios internos relevantes:
  - JWT hot path optimizado (sin query refresh_token para access tokens) y cache TTL corta de estado de revocacion.
  - `X-Request-ID` propagado en responses + logging estructurado por request.
  - metricas extendidas por endpoint/status/latencia manteniendo campos legacy.
  - cache TTL e invalidacion explicita para `/api/v2/questionnaires/active`.
  - optimizacion de paginado en session page v2 (query solo de paginas solicitadas).
  - mitigacion N+1 en listados de usuarios y problem reports.
  - lazy import de matplotlib para PDF/reportes.
  - ajuste conservador de defaults homelab y entrypoint gunicorn.
  - migracion de indices compuestos hot-path: `migrations/versions/20260510_01_add_perf_hotpath_indexes.py`.
- Validacion local completada: ruff, compileall, import sanity, pytest completo y k6 inspect (suite completa).
- Referencia preopt confirmada: baseline 10 VUs en produccion con degradacion severa (error rate ~32.70%, p95 ~7615 ms).
- Pendiente operativo para cierre total: ejecutar postopt en main (smoke, micro-baseline y baseline) con credenciales de usuario de prueba y evidencia versionada.
