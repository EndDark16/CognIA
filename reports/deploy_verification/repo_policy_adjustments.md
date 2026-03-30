# Repo Policy Adjustments (Deploy Validation)

## Hallazgo critico
- `models/` no puede ser excluido sin un mecanismo de descarga externa en runtime.

## Ajuste minimo propuesto
- Opcion A: mantener solo los binarios finales en `models/` dentro del repo.
- Opcion B: mover `models/` a storage externo y agregar paso de descarga en build/boot.

## Exclusiones seguras
- `artifacts/models/`, `artifacts/versioned_models/`, `data/processed*` pueden excluirse sin romper deploy.
