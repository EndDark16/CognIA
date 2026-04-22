# scenario_decision_report

## Resumen ejecutivo
- Mejor escenario global (BA media): psychologist_no_has.
- BA media caregiver: 0.5000
- BA media psychologist_no_has: 0.7579
- BA media psychologist_with_has: 0.7579

## Comparacion solicitada
- Perdida caregiver vs psychologist_with_has (BA): -0.2579
- Perdida psychologist_no_has vs psychologist_with_has (BA): 0.0000
- Aporte de has_*: no_material
- Dominio mas afectado al quitar has_* (d_ba minimo): adhd

## Lectura por escenario
- caregiver: flujo mas simple, menor cobertura de inputs y mayor dependencia de defaults.
- psychologist_no_has: mantiene casi todo el flujo psicologo, removiendo solo has_* y derivandolos cuando hay evidencia.
- psychologist_with_has: referencia de flujo psicologo completo.

## Recomendacion practica
- Producto: mantener psychologist_with_has como referencia clinica completa.
- Si se busca simplificar, psychologist_no_has es viable cuando la perdida no sea material en BA/PR-AUC.
- caregiver sigue usable para screening rapido, con caveat explicito por menor cobertura.

## Caveats
- Evaluacion sin reentrenar, con thresholds finales v15 y holdout strict_full.
- El alcance usa lineas finales vigentes: no-elimination final_hardening_v10 y elimination_clean_rebuild_v12.
