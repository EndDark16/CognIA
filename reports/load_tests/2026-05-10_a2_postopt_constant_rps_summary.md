# A2 postopt constant_rps

- Fecha UTC: 2026-05-10T23:18:39.591617+00:00
- Estado: no ejecutado.
- Motivo: tras `capacity_ladder` se activo criterio de parada por `http_req_failed > 5%` sostenido; se priorizo proteccion operacional del homelab y no escalar mas carga en la misma ventana.
- Evidencia de corte: `reports/load_tests/2026-05-10_a2_postopt_capacity_ladder_summary.md`.
- Nota: `constant_rps` quedo preparado y validado (`k6 inspect` OK), pendiente para ventana controlada adicional.
