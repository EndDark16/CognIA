# Elimination v11 final audit decision

Decision: `HOLD_V11_NEEDS_REVISION`

1) Mejora real: si numericamente.
2) Anti-leakage tecnico: pasa.
3) Ablacion: dependencia fuerte en señales cbcl_108/cbcl_112 y derivados.
4) Stress: razonable en missingness, fragil si cae cobertura cbcl.
5) Reemplazo baseline: no.
6) Caveat final: mantener caveat alto; aplicar confidence cap visible user[1%-99%], professional[0.5%-99.5%].

Hallazgo central:
- No se detecto fuga clasica de split/reuse.
- Si hay riesgo de pseudo-target: una regla simple con cbcl_108/cbcl_112 reproduce el rendimiento extremo del winner.
