# AGENTS.md

## Propósito del proyecto
Este repositorio implementa una tesis de ingeniería aplicada en salud mental infantil: un sistema de alerta temprana para niños de 6 a 11 años.

El sistema trabaja con 5 dominios:
- ADHD
- Conduct
- Elimination
- Anxiety
- Depression

Contexto metodológico:
- HBN es la base empírica.
- DSM-5 es el marco formal.
- Hay una capa interna diagnóstica exacta y una capa externa de 5 dominios.
- El entorno es simulado; no es un producto de diagnóstico clínico definitivo.

## Restricciones metodológicas no negociables
- No presentar resultados como diagnóstico automático o definitivo.
- No inventar equivalencias entre fuentes, instrumentos, modos o derivaciones.
- No introducir leakage, shortcuts, reuse silencioso de artefactos ni atajos metodológicos.
- No romper contratos de inferencia, API, cuestionario o outputs sin trazabilidad explícita.
- No sobreprometer métricas, cobertura, robustez ni validez clínica.
- Priorizar rigor metodológico, honestidad y reproducibilidad por encima de marketing o simplificación.

## Cómo razonar sobre claims clínicos y métricas
- Tratar las métricas como evidencia de screening/apoyo, no como validación clínica definitiva.
- Separar resultados globales, por dominio y por modo.
- Reportar incertidumbre, caveats y límites cuando haya cobertura parcial, señales débiles o equivalencias no estrictas.
- Si un dato o contrato no está confirmado en el repo, marcarlo como `por confirmar`.
- Evitar lenguaje absoluto; preferir formulaciones operativas como:
  - apto para screening
  - requiere caveat
  - no apto para interpretacion fuerte
  - evidencia suficiente para apoyo profesional

## Cómo trabajar en este repo
1. Explora antes de editar: revisa `README.md`, `AGENTS_CONTEXT.md`, `docs/openapi.yaml`, `docs/OPENAPI_GUIDE.md` y los artefactos relevantes.
2. No rompas pipeline ni contratos de inferencia: valida el impacto sobre API, runtime, cuestionario y outputs antes de cerrar cualquier cambio.
3. Mantén caveats y trazabilidad: toda decisión relevante debe quedar documentada en texto o en artefactos versionados.
4. Prefiere cambios pequeños y verificables antes que refactors amplios.
5. Si falta contexto técnico, busca evidencia en el repo primero; si sigue faltando, dilo explícitamente.

## Referencias de contexto
- `README.md`
- `AGENTS_CONTEXT.md`
- `docs/openapi.yaml`
- `docs/OPENAPI_GUIDE.md`
- `artifacts/inference_v4/` si existe; en caso contrario, `por confirmar`

## Estado conocido de Elimination
- Cierre comparativo revisado: `elimination_clean_rebuild_v12` vs `elimination_final_push_v14`.
- Decision vigente en los artefactos revisados: `KEEP_V12`.
- `v14` no aporta mejora neta sobre `v12` en los reportes de cierre revisados; tratarlo como exploratorio y no como reemplazo operativo.
- Si en otro contexto se usa `selected_models` o `selected_feature_set`, no asumir homologia entre campanas sin confirmar el reporte de cierre correspondiente.

## Cierre final de modelos
- La fuente de verdad para las versiones finales compatibles con el enfoque dual es `data/questionnaire_final_ceiling_v4/reports/final_caregiver_closure_decision.md`, `data/questionnaire_final_ceiling_v4/reports/final_psychologist_closure_decision.md` y `data/questionnaire_final_ceiling_v4/reports/final_global_closure_decision.md`.
- Esos cierres son los que deben usarse cuando se hable de `cuidador` y `psicologo`.
- El cierre por dominio en `reports/final_closure/final_model_metrics_compact.csv` y `reports/final_closure/final_domain_status_matrix.csv` queda como referencia historica de otra linea de trabajo, no como fuente principal para el enfoque dual.
- `elimination` sigue siendo el dominio mas debil y requiere caveat aun en el cierre final dual.
- El corte `v10+` es metodologico, no un sufijo universal en el nombre de cada modelo; cuando se pida "version" de un modelo, usar `model_version_final` del inventario auditado y, si no existe un tag numerico explicito, marcarlo como `por confirmar`.

## Actualizacion de estado (2026-04-06) - final_ceiling_check_v15
- IMPORTANTE: esta pasada de techo queda documentada como decision de cierre metodologico y referencia obligatoria para futuras ventanas de contexto.
- Se ejecuto una pasada final de verificacion de techo sin abrir una campana nueva de mejora.
- La ejecucion versionada quedo en `data/final_ceiling_check_v15/` y `artifacts/final_ceiling_check_v15/`.
- Script ejecutado: `scripts/run_final_ceiling_check_v15.py`.
- Manifest de salida: `artifacts/final_ceiling_check_v15/final_ceiling_check_v15_manifest.json`.
- Inventario final generado en `data/final_ceiling_check_v15/inventory/final_model_inventory.csv`.
- Fuente de verdad no-elimination confirmada: cierre dual `questionnaire_final_ceiling_v4` con `valid_from_version=final_hardening_v10`.
- Fuente de verdad elimination confirmada: `elimination_clean_rebuild_v12` con decision `KEEP_V12` sobre `v14`.
- Clasificacion de techo por modo/dominio (v15): `near_ceiling=8`, `ceiling_reached=1`, `marginal_room_left=1`, `meaningful_room_left=0`.
- Elimination queda `near_ceiling` en ambos modos con `uncertainty_preferred` y `runtime_strong_entry=False`.
- Unico caso fuera de techo estricto en v15: `psychologist/anxiety` como `marginal_room_left` (sin evidencia de margen material grande).
- Claim permitido: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.
- Estado de iteracion: no recomendada una nueva iteracion amplia de modelado salvo evidencia nueva fuera de ruido.
- `por confirmar`: identidad estricta cruzada entre campanas para algunas comparaciones historicas (marcada en `lineage_note` del inventario v15).
- `por confirmar`: version exacta congelada del runtime final si no esta explicitada en artefacto auditado.

## Regla de continuidad de contexto
- A partir de esta sesion, cualquier decision, cambio de estado o pendiente relevante debe reflejarse en `AGENTS.md` y `docs/HANDOFF.md` dentro de la misma ventana de trabajo.


## Actualizacion de estado (2026-04-07) - questionnaire_master_final_corrected
- Se genero `reports/questionnaire_design_inputs_v2/` con 7 artefactos de base estructurada para diseno de cuestionario.
- Se genero `questionnaire_master_final_corrected.csv` listo para importacion BD/runtime/API, con core cerrado y estructurado.
- Se genero auditoria `reports/questionnaire_master_final_audit_fix.md` y validacion `reports/questionnaire_master_final_validation.csv`.
- Alcance aplicado: solo modelos finales vigentes (no-elimination desde `final_hardening_v10`, elimination desde `elimination_clean_rebuild_v12`, decision `KEEP_V12`).
- No se incorporaron preguntas abiertas al input core del modelo.


## Actualizacion de estado (2026-04-12) - hybrid_rf_ceiling_push_v1
- Se ejecuto una campana completa de entrenamiento/auditoria para la base nueva `data/hybrid_dsm5_rebuild_v1/`.
- Linea versionada creada: `data/hybrid_rf_ceiling_push_v1/` y `artifacts/hybrid_rf_ceiling_push_v1/`.
- Script principal: `scripts/run_hybrid_rf_ceiling_push_v1.py`.
- Manifest de salida: `artifacts/hybrid_rf_ceiling_push_v1/hybrid_rf_ceiling_push_v1_manifest.json`.
- Cobertura modelada: 5 dominios x 6 modos = 30 pares modo-dominio.
- Holdout se mantuvo intocable durante busqueda; seleccion sobre validacion interna.
- Random Forest se mantuvo como linea principal obligatoria.
- Targets finales auditados por dominio en `data/hybrid_rf_ceiling_push_v1/tables/domain_target_registry.csv`.
- Regla de respondibilidad auditada por modo en `data/hybrid_rf_ceiling_push_v1/tables/mode_feature_coverage_matrix.csv`.
- Evidencia de sobreentrenamiento: `si` (parcial, no generalizada) segun `reports/hybrid_rf_overfitting_audit.md`.
- Evidencia de buena generalizacion global: `si` (26/30 pares con criterio fuerte) segun `reports/hybrid_rf_generalization_audit.md`.
- Comparacion full-mode vs linea previa: mejora material en 7/10 pares comparables (`data/hybrid_rf_ceiling_push_v1/tables/hybrid_rf_vs_previous_fullmode_delta.csv`).
- Estado de techo en esta campana: predominio `marginal_room_left` con casos `ceiling_reached`; ver `reports/hybrid_rf_ceiling_decision.md`.
- Caveat metodologico: resultados aptos para screening/apoyo profesional en entorno simulado, no diagnostico automatico.

## Actualizacion de estado (2026-04-12) - hybrid_rf_consolidation_v2
- Se ejecuto campana v2 de consolidacion final sobre la linea hibrida nueva, enfocada en auditoria quirurgica de candidatos (sin reexplorar 30 pares completos).
- Linea versionada creada: `data/hybrid_rf_consolidation_v2/` y `artifacts/hybrid_rf_consolidation_v2/`.
- Script ejecutado: `scripts/run_hybrid_rf_consolidation_v2.py`.
- Manifest: `artifacts/hybrid_rf_consolidation_v2/hybrid_rf_consolidation_v2_manifest.json`.
- Alcance auditado: 13 candidatos provisionales (ADHD, Anxiety, Conduct, Depression, Elimination) en modos 2/3 y full segun plan de consolidacion.
- Reproduccion de candidatos: `13/13` reproducidos materialmente vs v1.
- Decisiones de promocion: `PROMOTE_NOW=0`, `PROMOTE_WITH_CAVEAT=7`, `HOLD_FOR_TARGETED_FIX=6`, `REJECT_AS_PRIMARY=0`.
- Champions por dominio (v2):
  - `adhd`: `psychologist_full` (`PROMOTE_WITH_CAVEAT`)
  - `anxiety`: `caregiver_full` (`PROMOTE_WITH_CAVEAT`)
  - `conduct`: `psychologist_2_3` (`PROMOTE_WITH_CAVEAT`)
  - `depression`: `caregiver_2_3` (`HOLD_FOR_TARGETED_FIX`)
  - `elimination`: `caregiver_2_3` (`PROMOTE_WITH_CAVEAT`)
- Sobreentrenamiento en candidatos v2: evidencia parcial (`3/13` con gap alto train-val o val-holdout).
- DSM-5: aporte material detectado en los 5 dominios evaluados (`5/5` en resumen de ganancia hibrida vs clean-base).
- Claim permitido se mantiene: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-13) - hybrid_rf_final_ceiling_push_v3
- Se ejecuto campana v3 de optimizacion RF sobre la base `data/hybrid_dsm5_rebuild_v1/`.
- Linea versionada creada: `data/hybrid_rf_final_ceiling_push_v3/` y `artifacts/hybrid_rf_final_ceiling_push_v3/`.
- Script principal: `scripts/run_hybrid_rf_final_ceiling_push_v3.py`.
- Manifest: `artifacts/hybrid_rf_final_ceiling_push_v3/hybrid_rf_final_ceiling_push_v3_manifest.json`.
- Cobertura modelada: 30 pares modo-dominio (5 dominios x 6 modos) con holdout intocable.
- Busqueda ejecutada: RF con multiples configuraciones, weighting, calibracion y thresholding; mas auditorias de estabilidad, bootstrap, ablation y stress.
- Escala de entrenamiento v3: `trial_count=2850`, `winner_count=30`.
- Configuracion mas ganadora: `rf_positive_push_strong` (17/30 winners).
- Promotion decisions globales: `PROMOTE_NOW=13`, `PROMOTE_WITH_CAVEAT=6`, `HOLD_FOR_TARGETED_FIX=8`, `REJECT_AS_PRIMARY=3`.
- Champions por dominio:
  - `adhd -> psychologist_full (PROMOTE_NOW)`
  - `anxiety -> caregiver_2_3 (PROMOTE_NOW)`
  - `conduct -> psychologist_2_3 (PROMOTE_NOW)`
  - `depression -> caregiver_full (PROMOTE_WITH_CAVEAT)`
  - `elimination -> psychologist_2_3 (PROMOTE_NOW)`
- Sobreentrenamiento: evidencia parcial en `8/30` pares (gap train-val o val-holdout).
- Generalizacion fuerte: `25/30` pares cumplen criterio operativo.
- DSM-5 vs clean-base: ganancia material promedio positiva por dominio en BA y PR-AUC, con mayor impacto en Elimination.
- Estado de techo v3: predominio `marginal_room_left` con `ceiling_reached` en subconjunto (sin evidencia de `meaningful_room_left`).
- Claim permitido: evidencia apta para screening/apoyo profesional en entorno simulado, no diagnostico automatico.

## Actualizacion de estado (2026-04-13) - hybrid_rf_targeted_fix_v4
- Se ejecuto campana v4 quirurgica de remediacion final sobre candidatos fragiles de la linea hibrida.
- Linea versionada creada: `data/hybrid_rf_targeted_fix_v4/` y `artifacts/hybrid_rf_targeted_fix_v4/`.
- Script principal: `scripts/run_hybrid_rf_targeted_fix_v4.py`.
- Manifest: `artifacts/hybrid_rf_targeted_fix_v4/hybrid_rf_targeted_fix_v4_manifest.json`.
- Alcance focal: 17 candidatos (Depression 6 modos, ADHD modos cortos, Elimination 1/3 y 2/3 comparadores, Anxiety caregiver 1/3-2/3-full).
- Escala ejecutada: `fits_total=980`, `trees_total=311700`.
- Decisiones v4: `PROMOTE_NOW=0`, `PROMOTE_WITH_CAVEAT=2`, `CEILING_CONFIRMED_NO_MATERIAL_GAIN=2`, `HOLD_FOR_FINAL_LIMITATION=12`, `REJECT_AS_PRIMARY=1`.
- Ganancia material vs v3: 3/17 candidatos (`elimination__caregiver_1_3`, `depression__caregiver_2_3`, `anxiety__caregiver_1_3`).
- Sobreentrenamiento: evidencia parcial persiste (gaps altos en subset de candidatos).
- Generalizacion: aceptable en agregado focal (criterio operativo cumplido en 12/17; ratio 0.706).
- Champions por dominio tras merge v4+carry-forward v3:
  - `adhd -> psychologist_full` (carry-forward v3)
  - `anxiety -> caregiver_2_3` (v4, caveat)
  - `conduct -> psychologist_2_3` (carry-forward v3)
  - `depression -> psychologist_2_3` (v4, caveat)
  - `elimination -> psychologist_2_3` (v4, ceiling confirmed)
- Estado de cierre: no hay evidencia para cierre honesto total de modelado principal; persisten limitaciones en Depression y modos cortos de ADHD/Elimination.
- Claim permitido se mantiene: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-13) - hybrid_final_freeze_v1
- Se ejecuto consolidacion documental y operativa final (sin reentrenamiento masivo).
- Linea creada: `data/hybrid_final_freeze_v1/` y `artifacts/hybrid_final_freeze_v1/`.
- Script: `scripts/build_hybrid_final_freeze_v1.py`.
- Artefactos principales:
  - `tables/frozen_hybrid_champions_master.csv`
  - `tables/frozen_hybrid_champions_inputs_master.csv`
  - `tables/frozen_hybrid_domain_limitations.csv`
  - `reports/frozen_hybrid_final_status.md`
  - `reports/frozen_hybrid_questionnaire_coverage.md`
  - `artifacts/hybrid_final_freeze_v1/hybrid_final_freeze_v1_manifest.json`
- Consolidacion champions (30 pares): 17 pares tomados de v4 (mas reciente en foco fragil) + 13 pares carry-forward de v3.
- Estado final congelado por categoria:
  - `FROZEN_PRIMARY=9`
  - `FROZEN_WITH_CAVEAT=5`
  - `HOLD_FOR_LIMITATION=13`
  - `REJECT_AS_PRIMARY=1`
  - `CEILING_CONFIRMED_BEST_PRACTICAL_POINT=2`
- CSV maestro de inputs exportado con 223 features (`directos=180`, `derivados_transparentes=43`).
- Caveats de fuente (`por_confirmar`):
  - `hybrid_input_audit_classification_final.csv` no encontrado con ese nombre.
  - `hybrid_dataset_final_registry_v1.csv` no encontrado con ese nombre.
- Claim permitido se mantiene: evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-13) - hybrid_no_external_scores_rebuild_v2
- Se ejecuto una reconstruccion estricta del universo modelable para excluir puntajes/subescalas/cutoffs externos no compatibles con producto real.
- Linea nueva creada: `data/hybrid_no_external_scores_rebuild_v2/` y `artifacts/hybrid_no_external_scores_rebuild_v2/`.
- Script: `scripts/run_hybrid_no_external_scores_rebuild_v2.py`.
- Exclusiones explicitas aplicadas: 28/28 columnas prohibidas (SWAN, SDQ, ICUT, ARI, SCARED parent/self-report, MFQ total), mas otras columnas no modelables segun gobernanza para un total removido de 52 columnas.
- Universo retenido para modelado principal: 176 columnas originales (`directas=152`, `transparent_derived=24`) + 9 engineered internas trazables.
- Cobertura por modo recalculada y auditada en `modes/no_external_scores_mode_coverage.csv`; no hubo modos severamente empobrecidos.
- Se entrenaron los 30 pares dominio-modo con RF y auditorias de calibracion, threshold, bootstrap, seed stability, ablation y stress.
- Comparacion contra linea congelada previa: delta medio global `BA=-0.0285`, `PR-AUC=-0.0135`, `Recall=-0.0610`, `Precision=+0.0028`, `Brier=+0.0033`.
- Dominios que resistieron mejor la eliminacion: `anxiety`, `conduct`. Deterioro mas fuerte: `adhd` (tambien impacto relevante en `elimination` y `depression`).
- Modelos previos quedaron formalmente despromovidos en `inventory/previous_models_status_demoted.csv` con:
  - `historical_trace_only`
  - `not_functional_for_new_primary_line`
- Decision de viabilidad: linea limpia viable y metodologicamente alineada con producto real, con adopcion principal selectiva y caveats en pares fragiles.

## Actualizacion de estado (2026-04-13) - hybrid_no_external_scores_boosted_v3
- Se ejecuto campaña focalizada de mejora sobre la linea limpia (sin scores externos) con feature engineering interno + familias tabulares alternativas.
- Linea creada: `data/hybrid_no_external_scores_boosted_v3/` y `artifacts/hybrid_no_external_scores_boosted_v3/`.
- Script: `scripts/run_hybrid_no_external_scores_boosted_v3.py`.
- Pares priorizados: ADHD short (4), Depression (6), Elimination short (2), Anxiety caregiver_1_3 (1).
- Modelos probados (disponibles en entorno): RF, ExtraTrees, HistGradientBoosting, LogisticRegression; y boosting externos cuando disponibles (XGBoost, LightGBM, CatBoost) en subset pesado.
- Resultados: mejoras materiales de BA/PR-AUC/Recall en 13/13 pares priorizados vs v2; en varios casos con perdida de Precision (tradeoff documentado).
- Mejores familias observadas en v3: HGB y ExtraTrees dominaron en ADHD/Elimination/Anxiety; CatBoost lidero en Depression (caregiver_full) en este run.

## Actualizacion de estado (2026-04-13) - hybrid_operational_freeze_v1
- Se ejecuto freeze operativo final mixto basado en `hybrid_no_external_scores_rebuild_v2` con overrides selectivos desde `hybrid_no_external_scores_boosted_v3`.
- Linea creada: `data/hybrid_operational_freeze_v1/` y `artifacts/hybrid_operational_freeze_v1/`.
- Script: `scripts/build_hybrid_operational_freeze_v1.py`.
- Overrides tomados desde boosted_v3: 4 pares (depression caregiver_full, depression psychologist_full, elimination caregiver_1_3, elimination psychologist_1_3).
- Clasificacion final (30 pares): `ROBUST_PRIMARY=15`, `PRIMARY_WITH_CAVEAT=2`, `HOLD_FOR_LIMITATION=9`, `SUSPECT_EASY_DATASET_NEEDS_CAUTION=4`, `REJECT_AS_PRIMARY=0`.
- Casos con auditoria especial por facilidad de dataset: Conduct en caregiver_2_3, caregiver_full, psychologist_2_3, psychologist_full.
- Evidencia de sobreentrenamiento marcada en 2 pares (depression caregiver_1_3 y psychologist_1_3) segun gap train-val BA > 0.1 en v2.

## Actualizacion de estado (2026-04-13) - hybrid_active_modes_freeze_v1
- Se ejecuto activacion operativa total con modelo activo obligatorio para 30/30 pares dominio-modo.
- Linea creada: `data/hybrid_active_modes_freeze_v1/` y `artifacts/hybrid_active_modes_freeze_v1/`.
- Script: `scripts/build_hybrid_active_modes_freeze_v1.py`.
- Tabla de activacion: `tables/hybrid_active_models_30_modes.csv` con confianza (%) y banda por par.
- Distribucion operativa: `ACTIVE_HIGH_CONFIDENCE=15`, `ACTIVE_MODERATE_CONFIDENCE=6`, `ACTIVE_LOW_CONFIDENCE=0`, `ACTIVE_LIMITED_USE=9`.
- CSV maestro de inputs: `tables/hybrid_questionnaire_inputs_master.csv` con 203 inputs (`directos=152`, `derivados_transparentes=51`, `requires_internal_scoring=51`).
- Cobertura por modo confirmada sin vacios de modelo (5 dominios x 6 modos).

## Actualizacion de estado (2026-04-14) - questionnaire_backend_operational_v2
- Se implemento backend operacional v2 de extremo a extremo para cuestionarios con sesiones, inferencia, historial, share, PDF y dashboards.
- Migracion creada: `migrations/versions/20260414_01_add_questionnaire_backend_v2.py`.
- Nuevas entidades ORM v2 agregadas en `app/models.py` (catalogo, registro de modelos, sesiones/resultados, tags/acceso, reporting/auditoria).
- Nuevo API v2 agregado en `api/routes/questionnaire_v2.py` y registrado en `api/app.py`.
- Servicios nuevos:
  - `api/services/questionnaire_v2_loader_service.py` (ingesta idempotente de cuestionario/modelos desde CSV de verdad).
  - `api/services/questionnaire_v2_service.py` (sesiones paginadas, guardado parcial, submit/inferencia, comorbilidad, historial, tags, share, PDF, dashboards y report jobs).
- Script operativo creado: `scripts/bootstrap_questionnaire_backend_v2.py` con comandos:
  - `load-questionnaire`
  - `load-models`
  - `load-all`
  - `regenerate-report-snapshot`
- Contratos/arquitectura documentados en:
  - `docs/questionnaire_backend_architecture.md`
  - `docs/questionnaire_api_contract.md`
  - `docs/model_registry_and_inference.md`
  - `docs/reporting_and_dashboards.md`
  - `docs/migration_notes_questionnaire_v1.md`
- Caveat de integracion mantenido: para algunos `active_model_id` la ruta exacta de artefacto queda `por_confirmar`; runtime usa fallback trazable a champion por dominio sin reclamo diagnostico.
- Claim permitido sin cambios: evidencia apta para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-15) - deprecacion_legacy_questionnaires_v1_endpoints
- Se retiraron dos endpoints legacy de `api/v1/questionnaires` para reducir solapamiento funcional con `admin`:
  - `POST /api/v1/questionnaires/{template_id}/activate`
  - `POST /api/v1/questionnaires/active/clone`
- Reemplazos operativos vigentes:
  - publicacion de template: `POST /api/admin/questionnaires/{template_id}/publish`
  - clonacion de template: `POST /api/admin/questionnaires/{template_id}/clone`
- Se actualizaron pruebas y documentacion (`tests/test_questionnaires.py`, `tests/test_evaluations.py`, `docs/openapi.yaml`, `README.md`) para reflejar los reemplazos.
- Verificacion: suite completa en verde (`120 passed, 3 skipped`).

## Actualizacion de estado (2026-04-15) - problem_reports_backend_and_repo_policy
- Se implemento backend de reportes de problema end-to-end con persistencia, validacion, permisos y auditoria.
- Migracion nueva: `migrations/versions/20260415_01_add_problem_reports.py`.
- Nuevas tablas:
  - `problem_reports`
  - `problem_report_attachments`
  - `problem_report_audit_events`
- Nuevos componentes backend:
  - `api/routes/problem_reports.py`
  - `api/services/problem_report_service.py`
  - `api/schemas/problem_report_schema.py`
- Endpoints agregados:
  - `POST /api/problem-reports`
  - `GET /api/problem-reports/mine`
  - `GET /api/admin/problem-reports`
  - `GET /api/admin/problem-reports/{id}`
  - `PATCH /api/admin/problem-reports/{id}`
- Se agregaron variables de configuracion para uploads de reportes en `.env.example` y `config/settings.py`.
- Se actualizaron contratos/documentacion:
  - `docs/openapi.yaml`
  - `docs/problem_reporting_backend.md`
  - `docs/api_full_reference.md`
- Se formalizo politica de artefactos/versionado:
  - `docs/repository_artifact_policy.md`
  - ajuste de `.gitignore` y `.gitattributes`.

## Actualizacion de estado (2026-04-16) - render_boot_hotfix_optional_questionnaire_routes
- Se detecto fallo de arranque en deploy por import estricto de rutas no presentes en imagen:
  - `ModuleNotFoundError: No module named 'api.routes.questionnaire_runtime'`.
- Se aplico hotfix en `api/app.py`:
  - imports de `questionnaire_runtime` y `questionnaire_v2` ahora son opcionales (`try/except`).
  - registro de blueprints condicionado a disponibilidad real del modulo.
- Objetivo del hotfix: evitar caida total del worker cuando los modulos opcionales no estan versionados en la rama desplegada.
- Estado de ramas:
  - `dev.enddark` actualizado con commit `ed5f57e`.
  - `development` actualizado con commit `0067481`.

## Actualizacion de estado (2026-04-16) - questionnaire_runtime_v1_v2_versioned_complete
- Se versiono de forma completa el bloque backend de cuestionarios runtime/v2 que estaba solo en workspace local.
- Commit principal: `96d3ffe` sobre `dev.enddark`.
- Alcance versionado:
  - Rutas/API: `api/routes/questionnaire_runtime.py`, `api/routes/questionnaire_v2.py`.
  - Servicios: `api/services/questionnaire_runtime_service.py`, `api/services/questionnaire_v2_loader_service.py`, `api/services/questionnaire_v2_service.py`.
  - Schemas: `api/schemas/questionnaire_v2_schema.py`.
  - Migraciones faltantes en cadena Alembic:
    - `migrations/versions/20260330_01_add_questionnaire_runtime_v1.py`
    - `migrations/versions/20260414_01_add_questionnaire_backend_v2.py`
  - Script operativo: `scripts/bootstrap_questionnaire_backend_v2.py`.
  - Datos fuente minimos requeridos por loader v2:
    - `data/cuestionario_v16.4/*` (fuentes del cuestionario)
    - `data/hybrid_active_modes_freeze_v1/tables/*` (activacion 30 modos)
    - `data/hybrid_operational_freeze_v1/tables/hybrid_operational_final_champions.csv`
  - Documentacion tecnica asociada en `docs/` (arquitectura, contrato API, registry/inference, reporting, notas de migracion y openapi runtime).
  - Tests nuevos de API/servicios/smoke para runtime/v2.
- Verificacion en Docker Desktop:
  - `pytest tests/services/test_questionnaire_v2_loader.py tests/api/test_questionnaire_runtime_api.py tests/api/test_questionnaire_v2_api.py -q` => `10 passed`.
  - `pytest tests/models/test_questionnaire_runtime_service.py tests/smoke/test_questionnaire_runtime_smoke.py -q` => `4 passed`.
  - `alembic heads` => `20260415_01 (head)` con cadena de revisiones consistente.

## Actualizacion de estado (2026-04-16) - api_platform_hardening_openapi_alignment_v1
- Se ejecuto intervencion integral de plataforma API con foco en contratos, seguridad y coherencia repo/runtime.
- OpenAPI:
  - `docs/openapi.yaml` se alineo con inventario real de rutas montadas en runtime (incluye `questionnaire_runtime` v1, `questionnaire_v2`, dashboards/reportes y rutas de docs).
  - Se agregaron tags operativos: `QuestionnaireRuntime`, `QuestionnaireRuntimeAdmin`, `QuestionnaireV2`, `Dashboard`, `Reports`, `Docs`.
  - Se agregaron parametros reutilizables para query comun en v1/v2 (`months`, `mode`, `role`, `include_full`, `status`, `unread_only`, `runtime export mode`).
  - `docs/openapi_questionnaire_runtime_v1.yaml` se movio a `docs/archive/openapi/openapi_questionnaire_runtime_v1.yaml` como referencia historica (fuente activa unica: `docs/openapi.yaml`).
- Guardrail de contrato:
  - Test nuevo `tests/contracts/test_openapi_runtime_alignment.py` valida runtime real vs spec para evitar desalineacion futura.
- Seguridad/hardening backend:
  - `api/app.py` elimina fail-silent critico para blueprints opcionales mediante politica configurable:
    - `OPTIONAL_BLUEPRINTS_STRICT` (default `true`)
    - `OPTIONAL_BLUEPRINTS_REQUIRED` (default `questionnaire_runtime,questionnaire_v2`)
  - `api/routes/questionnaire_v2.py` y `api/routes/problem_reports.py` ya no exponen `str(exc)` en responses 5xx.
  - Se agrego rate limit a shared access publico v2 (`QV2_SHARED_ACCESS_RATE_LIMIT`, default `30 per minute`).
  - Se agrego validacion de path seguro para descarga PDF en v2 (`resolve_download_path`).
  - Se agrego validacion de firma binaria para adjuntos en problem reports (PNG/JPEG/WEBP), mitigando spoof MIME.
- DTOs/schemas:
  - Nuevo `api/schemas/questionnaire_runtime_schema.py` y adopcion en rutas runtime v1 para payloads user/professional/admin.
  - Normalizacion adicional en admin clone mediante `QuestionnaireCloneRequestSchema`.
- Repo/documentacion:
  - README, `docs/OPENAPI_GUIDE.md`, `docs/api_full_reference.md`, `docs/repository_artifact_policy.md`, `docs/repository_maintenance.md` actualizados.
  - Nueva evidencia de seguridad: `docs/security_hardening_20260416.md`.
- Verificacion parcial de regresion en esta ventana:
  - `pytest tests/api/test_app_blueprint_policy.py tests/api/test_questionnaire_v2_api.py tests/api/test_questionnaire_runtime_api.py tests/test_problem_reports.py tests/contracts/test_openapi_runtime_alignment.py -q` => `23 passed`.
- `por confirmar`:
  - resultado de suite completa `pytest -q` en esta misma ventana antes de cierre final.

## Actualizacion de estado (2026-04-17) - openapi_descripciones_es_endpoint_complete
- Se actualizaron las descripciones de endpoints en `docs/openapi.yaml` para cobertura completa en espanol.
- Cobertura final: `115/115` operaciones documentadas con `description` (sin omisiones).
- Cada descripcion ahora explicita, por endpoint:
  - objetivo funcional
  - ruta y metodo
  - requisitos de seguridad declarados en OpenAPI
  - parametros de entrada
  - body request (si aplica)
  - codigos de respuesta de exito/error documentados
- Validacion ejecutada:
  - parseo YAML: `openapi_yaml_valid`.
  - `pytest tests/contracts/test_openapi_runtime_alignment.py tests/test_docs_metrics.py tests/api/test_questionnaire_v2_api.py tests/test_problem_reports.py -q` => `21 passed`.

## Actualizacion de estado (2026-04-24) - hybrid_v6_quick_champion_guard_hotfix_v1
- Se ejecuto hotfix rapido y focal sobre champions activos v6 para hacer cumplir regla dura de guardia:
  - ningun champion activo con `recall|specificity|roc_auc|pr_auc > 0.98`.
- Script principal:
  - `scripts/run_hybrid_v6_quick_champion_guard_hotfix.py`
- Lineas versionadas nuevas:
  - `data/hybrid_v6_quick_champion_guard_hotfix_v1/`
  - `data/hybrid_operational_freeze_v6_hotfix_v1/`
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/`
  - `artifacts/hybrid_v6_quick_champion_guard_hotfix_v1/`
  - `artifacts/hybrid_operational_freeze_v6_hotfix_v1/`
  - `artifacts/hybrid_active_modes_freeze_v6_hotfix_v1/`
- Resultado:
  - `violating_slots_before=16`
  - `corrected_slots_total=16`
  - `remaining_guard_violations=0`
  - `policy_violations=0`
- Estrategia aplicada:
  - reemplazo directo con modelos existentes cuando habia candidato valido guard-compliant.
  - retrain ligero solo para slots sin reemplazo existente.
  - fallback DSM-5 core de 1 feature para evitar colapso de precision/F1 cuando el fallback debil era insuficiente.
- Integracion runtime:
  - `api/services/questionnaire_v2_loader_service.py` actualizado para defaults `*_freeze_v6_hotfix_v1`.
- Claim permitido sin cambios:
  - evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-04-24) - cierre operativo guardia dura v6_hotfix_v1
- Se realizo auditoria de cierre sobre `freeze_v6` y `freeze_v6_hotfix_v1` para confirmar estado real de violaciones.
- Resultado de auditoria:
  - `freeze_v6`: `16` slots violando guardia dura en al menos una metrica vigilada.
  - `freeze_v6_hotfix_v1`: `0` slots violando guardia dura.
- Fuente operativa confirmada para runtime/loader y contratos de inferencia:
  - `data/hybrid_active_modes_freeze_v6_hotfix_v1/tables/hybrid_active_models_30_modes.csv`
  - `data/hybrid_operational_freeze_v6_hotfix_v1/tables/hybrid_operational_final_champions.csv`
- Se actualizaron validaciones para tratar `v6_hotfix_v1` como linea activa en policy checks.

## Actualizacion de estado (2026-04-24) - coherencia confidence/clase v6_hotfix_v1
- Se auditaron los 30 champions activos reales cargados por `api/services/questionnaire_v2_loader_service.py`.
- Resultado de guardrails en la linea activa real:
  - `recall|specificity|roc_auc|pr_auc > 0.98`: `0` violadores.
- Incoherencias encontradas:
  - `12` filas con `ACTIVE_MODERATE_CONFIDENCE` y `confidence_band=high`.
  - varias de esas filas tenian caveat metodologico (`secondary metric anomaly`, `mode fragility` o `stress sensitivity`), por lo que `high` era comunicacionalmente excesivo.
- Correccion aplicada:
  - `ACTIVE_MODERATE_CONFIDENCE` queda con `confidence_band=moderate` y `confidence_pct<=84.9`.
  - `ACTIVE_LIMITED_USE` queda con `confidence_band=limited`.
  - `ACTIVE_HIGH_CONFIDENCE` queda reservado para `confidence_band=high` sin caveat metodologico fuerte.
- No se cambiaron `active_model_id`, metricas de modelo, inputs funcionales, outputs funcionales, `domain/mode/role` ni semantica operativa.
- Summary final activa: `ACTIVE_HIGH_CONFIDENCE/high=1`, `ACTIVE_MODERATE_CONFIDENCE/moderate=14`, `ACTIVE_LIMITED_USE/limited=15`.
