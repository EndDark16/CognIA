# Cuestionario Runtime v1 - Preguntas completas

Total de preguntas activas base: **42**

> Nota: esta version es la base operativa actual del backend (feature-driven).

## Inputs obligatorios actuales de modelos (runtime)

- Esta seccion lista los **inputs tecnicos que esperan los modelos** en runtime por dominio.
- Son obligatorios a nivel de binario/modelo. Si faltan respuestas, el backend hoy aplica defaults para completar el vector.
- Total de inputs unicos (union 5 dominios): **283**
- Inputs compartidos por los 5 dominios (interseccion): **15**
- Interseccion: `age_years`, `cbcl_aggressive_behavior_proxy`, `cbcl_anxious_depressed_proxy`, `cbcl_attention_problems_proxy`, `cbcl_externalizing_proxy`, `cbcl_internalizing_proxy`, `cbcl_rule_breaking_proxy`, `has_cbcl`, `has_sdq`, `sdq_conduct_problems`, `sdq_emotional_symptoms`, `sdq_hyperactivity_inattention`, `sdq_impact`, `sdq_total_difficulties`, `sex_assigned_at_birth`

### Dominio `adhd` (35 inputs obligatorios)

- `age_years`
- `sex_assigned_at_birth`
- `site`
- `release`
- `has_swan`
- `swan_hyperactive_impulsive_total`
- `swan_inattention_total`
- `swan_total`
- `has_conners`
- `conners_cognitive_problems`
- `conners_conduct_problems`
- `conners_hyperactivity`
- `conners_total`
- `has_cbcl`
- `cbcl_aggressive_behavior_proxy`
- `cbcl_anxious_depressed_proxy`
- `cbcl_attention_problems_proxy`
- `cbcl_externalizing_proxy`
- `cbcl_internalizing_proxy`
- `cbcl_rule_breaking_proxy`
- `has_sdq`
- `sdq_conduct_problems`
- `sdq_emotional_symptoms`
- `sdq_hyperactivity_inattention`
- `sdq_impact`
- `sdq_peer_problems`
- `sdq_prosocial_behavior`
- `sdq_total_difficulties`
- `has_ysr`
- `ysr_aggressive_behavior_proxy`
- `ysr_anxious_depressed_proxy`
- `ysr_attention_problems_proxy`
- `ysr_externalizing_proxy`
- `ysr_internalizing_proxy`
- `ysr_rule_breaking_proxy`

### Dominio `conduct` (23 inputs obligatorios)

- `age_years`
- `sex_assigned_at_birth`
- `site`
- `release`
- `has_icut`
- `icut_total`
- `has_ari_p`
- `ari_p_symptom_total`
- `has_ari_sr`
- `ari_sr_symptom_total`
- `has_cbcl`
- `cbcl_aggressive_behavior_proxy`
- `cbcl_anxious_depressed_proxy`
- `cbcl_attention_problems_proxy`
- `cbcl_externalizing_proxy`
- `cbcl_internalizing_proxy`
- `cbcl_rule_breaking_proxy`
- `has_sdq`
- `sdq_conduct_problems`
- `sdq_emotional_symptoms`
- `sdq_hyperactivity_inattention`
- `sdq_impact`
- `sdq_total_difficulties`

### Dominio `elimination` (17 inputs obligatorios)

- `age_years`
- `sex_assigned_at_birth`
- `site`
- `release`
- `has_cbcl`
- `cbcl_aggressive_behavior_proxy`
- `cbcl_anxious_depressed_proxy`
- `cbcl_attention_problems_proxy`
- `cbcl_externalizing_proxy`
- `cbcl_internalizing_proxy`
- `cbcl_rule_breaking_proxy`
- `has_sdq`
- `sdq_conduct_problems`
- `sdq_emotional_symptoms`
- `sdq_hyperactivity_inattention`
- `sdq_impact`
- `sdq_total_difficulties`

### Dominio `anxiety` (260 inputs obligatorios)

- `age_years`
- `sex_assigned_at_birth`
- `site`
- `release`
- `has_scared_p`
- `scared_p_01`
- `scared_p_02`
- `scared_p_03`
- `scared_p_04`
- `scared_p_05`
- `scared_p_06`
- `scared_p_07`
- `scared_p_08`
- `scared_p_09`
- `scared_p_10`
- `scared_p_11`
- `scared_p_12`
- `scared_p_13`
- `scared_p_14`
- `scared_p_15`
- `scared_p_16`
- `scared_p_17`
- `scared_p_18`
- `scared_p_19`
- `scared_p_20`
- `scared_p_21`
- `scared_p_22`
- `scared_p_23`
- `scared_p_24`
- `scared_p_25`
- `scared_p_26`
- `scared_p_27`
- `scared_p_28`
- `scared_p_29`
- `scared_p_30`
- `scared_p_31`
- `scared_p_32`
- `scared_p_33`
- `scared_p_34`
- `scared_p_35`
- `scared_p_36`
- `scared_p_37`
- `scared_p_38`
- `scared_p_39`
- `scared_p_40`
- `scared_p_41`
- `scared_p_generalized_anxiety`
- `scared_p_panic_somatic`
- `scared_p_possible_anxiety_disorder_cut25`
- `scared_p_school_avoidance`
- `scared_p_separation_anxiety`
- `scared_p_social_anxiety`
- `scared_p_total`
- `has_scared_sr`
- `scared_sr_01`
- `scared_sr_02`
- `scared_sr_03`
- `scared_sr_04`
- `scared_sr_05`
- `scared_sr_06`
- `scared_sr_07`
- `scared_sr_08`
- `scared_sr_09`
- `scared_sr_10`
- `scared_sr_11`
- `scared_sr_12`
- `scared_sr_13`
- `scared_sr_14`
- `scared_sr_15`
- `scared_sr_16`
- `scared_sr_17`
- `scared_sr_18`
- `scared_sr_19`
- `scared_sr_20`
- `scared_sr_21`
- `scared_sr_22`
- `scared_sr_23`
- `scared_sr_24`
- `scared_sr_25`
- `scared_sr_26`
- `scared_sr_27`
- `scared_sr_28`
- `scared_sr_29`
- `scared_sr_30`
- `scared_sr_31`
- `scared_sr_32`
- `scared_sr_33`
- `scared_sr_34`
- `scared_sr_35`
- `scared_sr_36`
- `scared_sr_37`
- `scared_sr_38`
- `scared_sr_39`
- `scared_sr_40`
- `scared_sr_41`
- `scared_sr_generalized_anxiety`
- `scared_sr_panic_somatic`
- `scared_sr_possible_anxiety_disorder_cut25`
- `scared_sr_school_avoidance`
- `scared_sr_separation_anxiety`
- `scared_sr_social_anxiety`
- `scared_sr_total`
- `has_cbcl`
- `cbcl_001`
- `cbcl_002`
- `cbcl_003`
- `cbcl_004`
- `cbcl_005`
- `cbcl_006`
- `cbcl_007`
- `cbcl_008`
- `cbcl_009`
- `cbcl_010`
- `cbcl_011`
- `cbcl_012`
- `cbcl_013`
- `cbcl_014`
- `cbcl_015`
- `cbcl_016`
- `cbcl_017`
- `cbcl_018`
- `cbcl_019`
- `cbcl_020`
- `cbcl_021`
- `cbcl_022`
- `cbcl_023`
- `cbcl_024`
- `cbcl_025`
- `cbcl_026`
- `cbcl_027`
- `cbcl_028`
- `cbcl_029`
- `cbcl_030`
- `cbcl_031`
- `cbcl_032`
- `cbcl_033`
- `cbcl_034`
- `cbcl_035`
- `cbcl_036`
- `cbcl_037`
- `cbcl_038`
- `cbcl_039`
- `cbcl_040`
- `cbcl_041`
- `cbcl_042`
- `cbcl_043`
- `cbcl_044`
- `cbcl_045`
- `cbcl_046`
- `cbcl_047`
- `cbcl_048`
- `cbcl_049`
- `cbcl_050`
- `cbcl_051`
- `cbcl_052`
- `cbcl_053`
- `cbcl_054`
- `cbcl_055`
- `cbcl_056`
- `cbcl_057`
- `cbcl_058`
- `cbcl_059`
- `cbcl_060`
- `cbcl_061`
- `cbcl_062`
- `cbcl_063`
- `cbcl_064`
- `cbcl_065`
- `cbcl_066`
- `cbcl_067`
- `cbcl_068`
- `cbcl_069`
- `cbcl_070`
- `cbcl_071`
- `cbcl_072`
- `cbcl_073`
- `cbcl_074`
- `cbcl_075`
- `cbcl_076`
- `cbcl_077`
- `cbcl_078`
- `cbcl_079`
- `cbcl_080`
- `cbcl_081`
- `cbcl_082`
- `cbcl_083`
- `cbcl_084`
- `cbcl_085`
- `cbcl_086`
- `cbcl_087`
- `cbcl_088`
- `cbcl_089`
- `cbcl_090`
- `cbcl_091`
- `cbcl_092`
- `cbcl_093`
- `cbcl_094`
- `cbcl_095`
- `cbcl_096`
- `cbcl_097`
- `cbcl_098`
- `cbcl_099`
- `cbcl_100`
- `cbcl_101`
- `cbcl_102`
- `cbcl_103`
- `cbcl_104`
- `cbcl_105`
- `cbcl_106`
- `cbcl_107`
- `cbcl_108`
- `cbcl_109`
- `cbcl_110`
- `cbcl_111`
- `cbcl_112`
- `cbcl_113`
- `cbcl_114`
- `cbcl_115`
- `cbcl_116`
- `cbcl_117`
- `cbcl_118`
- `cbcl_aggressive_behavior_proxy`
- `cbcl_anxious_depressed_proxy`
- `cbcl_attention_problems_proxy`
- `cbcl_externalizing_proxy`
- `cbcl_internalizing_proxy`
- `cbcl_rule_breaking_proxy`
- `has_sdq`
- `sdq_01`
- `sdq_02`
- `sdq_03`
- `sdq_04`
- `sdq_05`
- `sdq_06`
- `sdq_07`
- `sdq_08`
- `sdq_09`
- `sdq_10`
- `sdq_11`
- `sdq_12`
- `sdq_13`
- `sdq_14`
- `sdq_15`
- `sdq_16`
- `sdq_17`
- `sdq_18`
- `sdq_19`
- `sdq_20`
- `sdq_21`
- `sdq_22`
- `sdq_23`
- `sdq_24`
- `sdq_25`
- `sdq_conduct_problems`
- `sdq_emotional_symptoms`
- `sdq_hyperactivity_inattention`
- `sdq_impact`
- `sdq_peer_problems`
- `sdq_prosocial_behavior`
- `sdq_total_difficulties`

### Dominio `depression` (18 inputs obligatorios)

- `cbcl_internalizing_proxy`
- `cbcl_anxious_depressed_proxy`
- `mfq_p_total`
- `sdq_total_difficulties`
- `sdq_peer_problems`
- `sdq_emotional_symptoms`
- `sdq_hyperactivity_inattention`
- `sdq_conduct_problems`
- `sdq_prosocial_behavior`
- `sdq_impact`
- `cbcl_attention_problems_proxy`
- `cbcl_externalizing_proxy`
- `cbcl_aggressive_behavior_proxy`
- `cbcl_rule_breaking_proxy`
- `age_years`
- `has_cbcl`
- `has_sdq`
- `sex_assigned_at_birth`

## Seccion: `contexto` (4 preguntas)

### 1. `age_years`
- **Pregunta:** Reporte el valor para age years.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `6.0` a `11.0`
- **Requerida:** si
- **Branching/visibilidad:** sin regla (siempre visible)

### 2. `sex_assigned_at_birth`
- **Pregunta:** Reporte el valor para sex assigned at birth.
- **Tipo de respuesta:** `single_choice`
- **Opciones posibles:** `Female` (Femenino), `Male` (Masculino), `Unknown` (Prefiero no responder)
- **Requerida:** si
- **Branching/visibilidad:** sin regla (siempre visible)

### 3. `site`
- **Pregunta:** Reporte el valor para site.
- **Tipo de respuesta:** `single_choice`
- **Opciones posibles:** `CBIC` (CBIC), `CUNY` (CUNY), `RUBIC` (RUBIC), `Staten Island` (Staten Island)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 4. `release`
- **Pregunta:** Reporte el valor para release.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `11.0` a `11.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

## Seccion: `dominio_adhd` (7 preguntas)

### 5. `conners_cognitive_problems`
- **Pregunta:** Reporte el valor para conners cognitive problems.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `6.0` a `15.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_conners', 'operator': '==', 'value': 1}]}`

### 6. `has_conners`
- **Pregunta:** Reporte el valor para has conners.
- **Tipo de respuesta:** `boolean`
- **Opciones posibles:** `0` (0), `1` (1)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 7. `ysr_internalizing_proxy`
- **Pregunta:** Reporte el valor para ysr internalizing proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `3.0` a `32.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 8. `ysr_externalizing_proxy`
- **Pregunta:** Reporte el valor para ysr externalizing proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `4.0` a `39.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 9. `ysr_attention_problems_proxy`
- **Pregunta:** Reporte el valor para ysr attention problems proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `20.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 10. `cbcl_attention_problems_proxy`
- **Pregunta:** Reporte el valor para cbcl attention problems proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `20.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 11. `sdq_hyperactivity_inattention`
- **Pregunta:** Reporte el valor para sdq hyperactivity inattention.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `10.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

## Seccion: `dominio_conduct` (9 preguntas)

### 12. `ysr_rule_breaking_proxy`
- **Pregunta:** Reporte el valor para ysr rule breaking proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `1.0` a `17.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 13. `ari_sr_symptom_total`
- **Pregunta:** Reporte el valor para ari sr symptom total.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `12.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_ari_p', 'operator': '==', 'value': 1}]}`

### 14. `cbcl_rule_breaking_proxy`
- **Pregunta:** Reporte el valor para cbcl rule breaking proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `22.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 15. `has_icut`
- **Pregunta:** Reporte el valor para has icut.
- **Tipo de respuesta:** `boolean`
- **Opciones posibles:** `0` (0), `1` (1)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 16. `icut_total`
- **Pregunta:** Reporte el valor para icut total.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `6.0` a `60.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_icut', 'operator': '==', 'value': 1}]}`

### 17. `has_ari_p`
- **Pregunta:** Reporte el valor para has ari p.
- **Tipo de respuesta:** `boolean`
- **Opciones posibles:** `0` (0), `1` (1)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 18. `has_ari_sr`
- **Pregunta:** Reporte el valor para has ari sr.
- **Tipo de respuesta:** `boolean`
- **Opciones posibles:** `0` (0), `1` (1)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 19. `cbcl_aggressive_behavior_proxy`
- **Pregunta:** Reporte el valor para cbcl aggressive behavior proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `1.0` a `19.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 20. `sdq_conduct_problems`
- **Pregunta:** Reporte el valor para sdq conduct problems.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `10.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

## Seccion: `dominio_elimination` (18 preguntas)

### 21. `cbcl_internalizing_proxy`
- **Pregunta:** Reporte el valor para cbcl internalizing proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `38.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 22. `sdq_prosocial_behavior`
- **Pregunta:** Reporte el valor para sdq prosocial behavior.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `8.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 23. `cbcl_externalizing_proxy`
- **Pregunta:** Reporte el valor para cbcl externalizing proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `2.0` a `40.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 24. `sdq_emotional_symptoms`
- **Pregunta:** Reporte el valor para sdq emotional symptoms.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `8.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 25. `sdq_impact`
- **Pregunta:** Reporte el valor para sdq impact.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `7.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 26. `sdq_total_difficulties`
- **Pregunta:** Reporte el valor para sdq total difficulties.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `38.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 27. `cbcl_025`
- **Pregunta:** Reporte el valor para cbcl 025.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 28. `cbcl_070`
- **Pregunta:** Reporte el valor para cbcl 070.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 29. `cbcl_057`
- **Pregunta:** Reporte el valor para cbcl 057.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 30. `cbcl_058`
- **Pregunta:** Reporte el valor para cbcl 058.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 31. `cbcl_060`
- **Pregunta:** Reporte el valor para cbcl 060.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 32. `cbcl_061`
- **Pregunta:** Reporte el valor para cbcl 061.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 33. `cbcl_062`
- **Pregunta:** Reporte el valor para cbcl 062.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 34. `cbcl_063`
- **Pregunta:** Reporte el valor para cbcl 063.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 35. `cbcl_064`
- **Pregunta:** Reporte el valor para cbcl 064.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 36. `cbcl_065`
- **Pregunta:** Reporte el valor para cbcl 065.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 37. `cbcl_066`
- **Pregunta:** Reporte el valor para cbcl 066.
- **Tipo de respuesta:** `likert_single`
- **Rango esperado:** `0.0` a `2.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 38. `sdq_peer_problems`
- **Pregunta:** Reporte el valor para sdq peer problems.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `10.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

## Seccion: `dominio_depression` (3 preguntas)

### 39. `ysr_anxious_depressed_proxy`
- **Pregunta:** Reporte el valor para ysr anxious depressed proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `18.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

### 40. `cbcl_anxious_depressed_proxy`
- **Pregunta:** Reporte el valor para cbcl anxious depressed proxy.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `20.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** `{'all': [{'feature_key': 'has_cbcl', 'operator': '==', 'value': 1}]}`

### 41. `mfq_p_total`
- **Pregunta:** Reporte el valor para mfq p total.
- **Tipo de respuesta:** `integer`
- **Rango esperado:** `0.0` a `60.0`
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)

## Seccion: `dominio_general` (1 preguntas)

### 42. `has_cbcl`
- **Pregunta:** Reporte el valor para has cbcl.
- **Tipo de respuesta:** `boolean`
- **Opciones posibles:** `0` (0), `1` (1)
- **Requerida:** no (opcional)
- **Branching/visibilidad:** sin regla (siempre visible)
