# Improvement hypotheses

hypothesis_id applies_to_mode applies_to_domain                                                       rationale expected_gain   risk priority
          H01       caregiver               all                   RF tuning agresivo con control de sobreajuste        medium medium     high
          H02    psychologist               all               RF tuning para cobertura completa con estabilidad        medium medium     high
          H03            both               all            calibracion isotonic/platt segun brier en validacion         small    low     high
          H04       caregiver           anxiety        threshold balanceado para reducir sesgo precision/recall        medium    low     high
          H05            both       elimination                  threshold precision_guarded para controlar FPs        medium medium     high
          H06            both              adhd                               feature hardening por missingness         small    low     high
          H07            both        depression             profile estable para disminuir sensibilidad parcial         small    low     high
          H08            both               all stress-based selection: penalizar alta sensibilidad a faltantes         small    low   medium
          H09    psychologist               all                 operating point profesional para alta confianza         small medium   medium
          H10       caregiver               all               perfil hardened_missing para disminuir fragilidad         small    low   medium
