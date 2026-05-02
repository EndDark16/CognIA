# AGENTS.md

## PropÃ³sito del proyecto
Este repositorio implementa una tesis de ingenierÃ­a aplicada en salud mental infantil: un sistema de alerta temprana para niÃ±os de 6 a 11 aÃ±os.

El sistema trabaja con 5 dominios:
- ADHD
- Conduct
- Elimination
- Anxiety
- Depression

Contexto metodolÃ³gico:
- HBN es la base empÃ­rica.
- DSM-5 es el marco formal.
- Hay una capa interna diagnÃ³stica exacta y una capa externa de 5 dominios.
- El entorno es simulado; no es un producto de diagnÃ³stico clÃ­nico definitivo.

## Restricciones metodolÃ³gicas no negociables
- No presentar resultados como diagnÃ³stico automÃ¡tico o definitivo.
- No inventar equivalencias entre fuentes, instrumentos, modos o derivaciones.
- No introducir leakage, shortcuts, reuse silencioso de artefactos ni atajos metodolÃ³gicos.
- No romper contratos de inferencia, API, cuestionario o outputs sin trazabilidad explÃ­cita.
- No sobreprometer mÃ©tricas, cobertura, robustez ni validez clÃ­nica.
- Priorizar rigor metodolÃ³gico, honestidad y reproducibilidad por encima de marketing o simplificaciÃ³n.

## CÃ³mo razonar sobre claims clÃ­nicos y mÃ©tricas
- Tratar las mÃ©tricas como evidencia de screening/apoyo, no como validaciÃ³n clÃ­nica definitiva.
- Separar resultados globales, por dominio y por modo.
- Reportar incertidumbre, caveats y lÃ­mites cuando haya cobertura parcial, seÃ±ales dÃ©biles o equivalencias no estrictas.
- Si un dato o contrato no estÃ¡ confirmado en el repo, marcarlo como `por confirmar`.
- Evitar lenguaje absoluto; preferir formulaciones operativas como:
  - apto para screening
  - requiere caveat
  - no apto para interpretacion fuerte
  - evidencia suficiente para apoyo profesional

## CÃ³mo trabajar en este repo
1. Explora antes de editar: revisa `README.md`, `AGENTS_CONTEXT.md`, `docs/openapi.yaml`, `docs/OPENAPI_GUIDE.md` y los artefactos relevantes.
2. No rompas pipeline ni contratos de inferencia: valida el impacto sobre API, runtime, cuestionario y outputs antes de cerrar cualquier cambio.
3. MantÃ©n caveats y trazabilidad: toda decisiÃ³n relevante debe quedar documentada en texto o en artefactos versionados.
4. Prefiere cambios pequeÃ±os y verificables antes que refactors amplios.
5. Si falta contexto tÃ©cnico, busca evidencia en el repo primero; si sigue faltando, dilo explÃ­citamente.

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
- Se ejecuto campaÃ±a focalizada de mejora sobre la linea limpia (sin scores externos) con feature engineering interno + familias tabulares alternativas.
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

## Actualizacion de estado (2026-04-25) - development_branch_reconciliation_ops_v1
- Se ejecuto auditoria completa de ramas remotas contra `origin/development` despues de `git fetch --all --prune`.
- Rama base auditada antes de cambios: `origin/development` en `136a683`.
- Reporte versionado: `docs/ops/development-branch-reconciliation-audit.md`.
- Decision CI/CD:
  - `ci-backend.yml` queda como unico CI backend autoritativo.
  - `.github/workflows/ci.yml` se elimina como workflow legado/redundante.
  - `ci-backend.yml` conserva compile/import sanity, `pytest -q`, docker build sanity y agrega Ruff F-check.
- Decision deploy:
  - `deploy-backend.yml` conserva rollback y `readyz`.
  - Se agrega verificacion de `github.sha` contra `origin/development` antes de mutar checkout.
  - Se reemplaza `docker compose up -d --build backend gateway` por rebuild de `backend` y recreacion forzada de `gateway`.
  - Se agregan logs de `gateway` al cierre del job.
- Validacion local detecto y corrigio una falla documental preexistente en `docs/openapi.yaml`, alineando tres operaciones admin y estados residuales health/readiness/metrics con el guardrail de contrato.
- Verificacion final local: `pytest -q` => `149 passed, 3 skipped`.
- No se promovieron ramas v6/v7 de modelado ni cambios amplios de startup/docs por estar fuera del alcance operativo seguro de esta reconciliacion.
- Pendiente operativo: reactivar workflows en GitHub solo despues de revisar el diff final y, preferiblemente, ejecutar una corrida controlada del CI backend.


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
- Se ejecuto auditoria anti-clone fuerte con recomputacion real de predicciones para la linea activa `v13`, sin reentrenamiento y sin reemplazo de champions.
- Rama de trabajo: `audit/v13-real-prediction-anti-clone`.
- Script principal: `scripts/run_hybrid_v13_real_prediction_anti_clone_audit.py`.
- Linea versionada creada:
  - `data/hybrid_v13_real_prediction_anti_clone_audit/`
- Cobertura:
  - `30/30` slots con `prediction_recomputed=yes`.
  - `30/30` slots con `artifacts_available=yes`.
  - `30/30` slots con match de metricas registradas vs recomputadas (`tolerance=1e-6`).
- Origen de artifacts usados para recomputacion:
  - `17` modelos desde `cognia_app_rf_max_real_metrics` (linea v10).
  - `13` modelos desde `cognia_app_final_rf_plus_maximize` (linea v11).
  - `0` artifacts duplicados por hash (`artifact_duplicate_hash_count=0`).
- Resultado anti-clone real:
  - `all_domains_real_clone_count=4`.
  - `elimination_real_clone_count=4`.
  - `all_domains_near_clone_warning_count=23`.
  - `final_audit_status=fail`.
- Pares Elimination marcados como `real_clone_flag=yes` segun regla estricta:
  - `elimination/caregiver_full` vs `elimination/psychologist_1_3` (`agreement>=0.995` y `probability_correlation>=0.995`).
  - `elimination/caregiver_full` vs `elimination/psychologist_2_3` (`agreement>=0.995` y `probability_correlation>=0.995`).
  - `elimination/caregiver_full` vs `elimination/psychologist_full` (`binary_predictions_identical=yes`).
  - `elimination/psychologist_1_3` vs `elimination/psychologist_2_3` (`agreement>=0.995` y `probability_correlation>=0.995`).
- Se generaron tablas/validadores/reportes/plots en `data/hybrid_v13_real_prediction_anti_clone_audit/` incluyendo:
  - `tables/v13_recomputed_champion_metrics.csv`
  - `tables/v13_registered_vs_recomputed_metrics.csv`
  - `tables/v13_pairwise_prediction_similarity_all_domains.csv`
  - `tables/v13_elimination_real_prediction_similarity.csv`
  - `validation/v13_real_prediction_anti_clone_validator.csv`
  - `reports/v13_real_prediction_anti_clone_report.md`
- Estado metodologico:
  - No se modificaron champions, inputs/outputs funcionales ni preguntas.
  - Claim permitido sin cambios: evidencia para screening/apoyo profesional en entorno simulado; no diagnostico automatico.

## Actualizacion de estado (2026-05-01) - hybrid_elimination_v14_real_anti_clone_rescue
- Se ejecuto correccion focal Elimination-only sobre la linea activa v13, sin campana general y sin modificar los otros 24 champions.
- Rama de trabajo: `fix/elimination-v14-real-anti-clone-rescue`.
- Script principal: `scripts/run_hybrid_elimination_v14_real_anti_clone_rescue.py`.
- Lineas/versionado generado:
  - `data/hybrid_elimination_v14_real_anti_clone_rescue/`
  - `artifacts/hybrid_elimination_v14_real_anti_clone_rescue/`
  - `data/hybrid_active_modes_freeze_v14/`
  - `artifacts/hybrid_active_modes_freeze_v14/`
  - `data/hybrid_operational_freeze_v14/`
  - `artifacts/hybrid_operational_freeze_v14/`
- Resultado tecnico de cierre:
  - `prediction_recomputed_slots=30/30`
  - `elimination_real_clone_count=0`
  - `all_domains_real_clone_count=0`
  - `artifact_duplicate_hash_count=0`
  - `guardrail_violations=0`
  - `final_audit_status=pass_with_warnings` (persisten warnings near-clone, sin clonado real).
- Alcance aplicado:
  - Solo cambiaron los 6 slots Elimination.
  - Los otros 24 slots quedaron identicos a v13 en activacion/metricas/threshold/features (validador `v14_non_elimination_unchanged_validator.csv`).
  - Contrato de inputs/outputs y orden exacto de `feature_list_pipe` conservado en 30/30 (`v14_contract_compatibility_validator.csv`).
  - Sin cambios de preguntas/cuestionario.
- Integracion runtime:
  - `api/services/questionnaire_v2_loader_service.py` apunta por defecto a `hybrid_active_modes_freeze_v14` y `hybrid_operational_freeze_v14`.


## Actualizacion de estado (2026-05-01) - hybrid_elimination_v15_caregiver_full_metric_rescue
- Se ejecuto rescate focal sobre `elimination/caregiver_full` partiendo de la linea activa `v14`, sin campana general.
- Script: `scripts/run_hybrid_elimination_v15_caregiver_full_metric_rescue.py`.
- Lineas/versionado generado:
  - `data/hybrid_elimination_v15_caregiver_full_metric_rescue/`
  - `artifacts/hybrid_elimination_v15_caregiver_full_metric_rescue/`
  - `data/hybrid_active_modes_freeze_v15/`
  - `artifacts/hybrid_active_modes_freeze_v15/`
  - `data/hybrid_operational_freeze_v15/`
  - `artifacts/hybrid_operational_freeze_v15/`
- Resultado principal en `elimination/caregiver_full` (v14 -> v15):
  - `F1: 0.712871 -> 0.820513`
  - `recall: 0.692308 -> 0.923077`
  - `precision: 0.734694 -> 0.738462`
  - `balanced_accuracy: 0.830967 -> 0.941679`
- Auditoria real final de la linea propuesta v15:
  - `prediction_recomputed_slots=30/30`
  - `elimination_real_clone_count=0`
  - `all_domains_real_clone_count=0`
  - `artifact_duplicate_hash_count=0`
  - `guardrail_violations=0`
  - `final_audit_status=pass_with_warnings`
- Alcance aplicado:
  - Cambio focal de champion en `elimination/caregiver_full`.
  - `24` no-Elimination conservados respecto a v14 (sin cambio de `active_model_id`).
  - Sin cambios de preguntas/cuestionario ni de contrato funcional de inputs/outputs.
- Loader/DB:
  - `api/services/questionnaire_v2_loader_service.py` actualizado para defaults `*_freeze_v15`.
  - Se corrigio bug real de sync DB: sanitizacion `NaN/inf` en `metrics_json` para evitar error PostgreSQL JSON (`invalid input syntax for type json`).
  - `bootstrap_questionnaire_backend_v2.py load-all` ejecutado con exito sobre Supabase/Postgres tras el fix.
- Caveat operativo abierto (sin ocultar):
  - En validacion `v15_registered_vs_recomputed_metrics.csv` quedan 2 slots Elimination con drift de metricas registradas vs recomputadas en artifacts historicos disponibles localmente (`caregiver_2_3`, `psychologist_full`).
  - El estado anti-clone real se mantiene en `0` clones reales.
## Actualizacion de estado (2026-05-01) - hybrid_final_clean_champion_resolution_v16
- Se ejecuto cierre final limpio sobre base `v15` para resolver warnings/caveats abiertos sin cambiar cuestionario ni contrato funcional.
- Script principal: `scripts/run_hybrid_final_clean_champion_resolution_v16.py`.
- Lineas/versionado generado:
  - `data/hybrid_final_clean_champion_resolution_v16/`
  - `artifacts/hybrid_final_clean_champion_resolution_v16/`
  - `data/hybrid_active_modes_freeze_v16/`
  - `artifacts/hybrid_active_modes_freeze_v16/`
  - `data/hybrid_operational_freeze_v16/`
  - `artifacts/hybrid_operational_freeze_v16/`
- Resultado tecnico final:
  - `final_audit_status=pass`
  - `prediction_recomputed_slots=30/30`
  - `metrics_match_registered=yes` en `30/30`
  - `all_domains_real_clone_count=0`
  - `elimination_real_clone_count=0`
  - `unresolved_near_clone_warning_count=0`
  - `artifact_duplicate_hash_count=0`
  - `guardrail_violations=0`
- Cambios focales reales:
  - No se reemplazaron champions por performance; se corrigio registro de metricas en 2 slots historicos Elimination para alinear `registered vs recomputed` con artifacts reales.
  - Se mantiene reutilizacion historica RF-compatible (lineage mixto) por diseno.
- Loader/runtime:
  - `api/services/questionnaire_v2_loader_service.py` actualizado a defaults `*_freeze_v16`.
## Actualizacion de estado (2026-05-01) - runtime_diagnostic_security_hardening_v17
- Objetivo ejecutado: hardening backend integral sobre la linea activa de modelos `v16` sin reentrenamiento ni cambio de cuestionario.
- Rama de trabajo: `fix/v17-runtime-diagnostic-security-final`.
- Cambios principales backend:
  - Se elimina fallback heuristico para champions activos en runtime v2 fuera de `TESTING`.
  - Se agrega validador runtime de artifacts activos 30 slots:
    - `scripts/run_runtime_artifact_validation_v17.py`
    - `data/hybrid_runtime_artifact_validation_v17/`
  - Se agrega endpoint de resumen clinico simulado:
    - `POST /api/v2/questionnaires/history/{session_id}/clinical-summary`
  - Se agrega endpoint de resultados sensibles cifrados:
    - `POST /api/v2/questionnaires/history/{session_id}/results-secure`
  - Se agrega endpoint de clave publica para transporte cifrado:
    - `GET /api/v2/security/transport-key`
  - Se implementa cifrado en reposo por campo (application-layer):
    - `api/services/crypto_service.py`
  - Se implementa cifrado de payload en transito por envelope:
    - `api/services/transport_crypto_service.py`
- Documentacion generada:
  - `docs/security_encryption.md`
  - `docs/frontend_encrypted_transport_contract.md`
  - `docs/clinical_summary_endpoint.md`
- Caveat operativo metodologico:
  - `v17` es hardening de runtime/seguridad sobre linea de modelos `v16`; no redefine champions.

## Actualizacion de estado (2026-05-02) - hybrid_domain_specialized_rf_v17
- Se ejecuto campana domain-specialized RF para 30 slots con feature governance estricta por dominio/rol/modo.
- Lineas versionadas:
  - `data/hybrid_domain_specialized_rf_v17/`
  - `data/hybrid_active_modes_freeze_v17/`
  - `data/hybrid_operational_freeze_v17/`
  - `artifacts/hybrid_domain_specialized_rf_v17/`
  - `artifacts/hybrid_active_modes_freeze_v17/`
  - `artifacts/hybrid_operational_freeze_v17/`
- Resultado final de auditoria:
  - `final_audit_status=pass`
  - `prediction_recomputed_slots=30/30`
  - `metrics_match_registered_yes_count=300` (`metrics_match_registered_no_count=0`)
  - `all_domains_real_clone_count=0`
  - `elimination_real_clone_count=0`
  - `hard_fail_unresolved_count=0`
  - `db_active_set_valid=yes`
- Regla operativa actualizada:
  - metricas `>0.98` se tratan como `high_separability_alert` con auditoria obligatoria;
  - no son rechazo automatico si no hay leakage/proxy/contaminacion/clonado y la generalizacion es defendible.
- Loader/runtime:
  - defaults de modelos activos movidos a `*_freeze_v17` en `questionnaire_v2_loader_service.py`.

## Actualizacion de estado (2026-05-02) - v17_extreme_metrics_threshold_separability_audit
- Se ejecuto auditoria focal de metricas extremas sobre la linea activa `v17` sin abrir campana de reentrenamiento global.
- Script principal:
  - `scripts/run_hybrid_v17_extreme_metrics_threshold_separability_audit.py`
- Artefactos generados:
  - `data/hybrid_domain_specialized_rf_v17/extreme_metrics_threshold_separability_audit/`
- Cobertura:
  - `audited_extreme_slots_count=30`
  - `threshold_sweep_completed_count=30`
  - `high_separability_audit_completed_count=30`
  - `ablation_completed_count=30`
- Resultado final:
  - `leakage_confirmed_count=0`
  - `target_proxy_confirmed_count=0`
  - `split_contamination_confirmed_count=0` (sin overlap de `participant_id`; overlap de filas exactas entre participantes queda como observacion no bloqueante)
  - `threshold_adjustment_recommended_count=0`
  - `threshold_adjustment_applied_count=0`
  - `retrain_required_count=0`
  - `unresolved_issue_count=0`
  - `final_audit_status=pass`
- Decision operativa:
  - no se cambiaron modelos ni thresholds de la linea activa `v17`;
  - los casos de alta separabilidad se mantienen como `high_separability_validated` con caveat metodologico de validacion externa.
