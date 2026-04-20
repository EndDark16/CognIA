# Three-path decision analysis

## Macro comparison
- Ruta A BA macro: **0.7945**
- Ruta B BA macro: **0.7978**
- Ruta C BA macro: **0.8984**
- Ganador macro por BA: **C_remodel_caregiver_contract**

## Ganador por dominio (BA)
- `adhd` -> ganador: **B_intermediate_mapping** (A=0.8859, B=0.8908, C=0.8815)
- `conduct` -> ganador: **C_remodel_caregiver_contract** (A=0.8913, B=0.9076, C=0.9229)
- `elimination` -> ganador: **C_remodel_caregiver_contract** (A=0.6836, B=0.6876, C=0.8055)
- `anxiety` -> ganador: **C_remodel_caregiver_contract** (A=0.8523, B=0.8409, C=0.9462)
- `depression` -> ganador: **C_remodel_caregiver_contract** (A=0.6594, B=0.6623, C=0.9361)

## Lectura metodológica
- Ruta A es útil como baseline operativo simple, pero sufre cuando faltan familias enteras no respondibles por cuidador.
- Ruta B recupera parcialmente rendimiento vía proxies e imputación, a costa de mayor riesgo metodológico y dependencia de supuestos.
- Ruta C alinea contrato de entrada con entrenamiento y reduce dependencia de defaults/fallbacks del runtime histórico.

- Nota: la comparacion de estabilidad por split (strict_full vs research_full) es limitada porque ambos split sets son equivalentes en IDs de test en esta version del repositorio.
