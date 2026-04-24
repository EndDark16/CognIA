# Input breakdown summary (runtime legacy unique inputs)

- Total unique runtime inputs: **283**

## Totales exactos solicitados
1. Direct questions (no derived/no system/no has_*): **237**
2. Derived: **34**
3. Presence flags (has_*): **10**
4. System-filled: **2**
5. Self-report only: **59**
6. Caregiver answerable: **224**
7. Answerable only in psychologist mode: **59**
8. Inputs disponibles por modo:
   - Modo cuidador sin self-report: **224**
   - Modo cuidador con self-report administrado: **283**
   - Modo psicologo completo: **283**

## Estimacion de tiempo (preguntas directas)
Supuesto: simple 4-6s, clinica 8-12s; derived/system no se preguntan directo.
- Cuidador sin self-report: 203 preguntas directas (12 simples, 191 clinicas) -> **26.3 a 39.4 min**
- Cuidador con self-report administrado: 247 preguntas directas (12 simples, 235 clinicas) -> **32.1 a 48.2 min**
- Psicologo completo: 247 preguntas directas (12 simples, 235 clinicas) -> **32.1 a 48.2 min**

## Nota de interpretacion
- Estos tiempos reflejan cubrir TODO el espacio legacy de 283 inputs; no son un cuestionario UX-optimizado.
- Para producto real, normalmente se reduce longitud via seleccion de bloques y/o modelado adaptado por modo.
