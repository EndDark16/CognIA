# Docker Compose Supabase Production Profile Audit

## Contexto
Se audito `docker-compose.yml` para evitar que despliegues productivos usen un Postgres local cuando la base oficial de produccion es Supabase.

## Causa raiz
El compose previo reutilizaba `DB_*` para dos objetivos distintos:
- conexion de la aplicacion (`backend -> DB_*`)
- inicializacion del contenedor local Postgres (`db -> POSTGRES_*`, pero apuntando a `DB_*`)

Esa mezcla permitia que credenciales de Supabase terminaran en el Postgres local, generando errores tipo `role ... does not exist` y ruido operativo en produccion.

## Cambios aplicados
1. `docker-compose.yml`
- `db` renombrado a `postgres` y movido a `profiles: ["local-db"]`.
- `POSTGRES_*` separados de `DB_*`.
- puerto local endurecido a `127.0.0.1:5432:5432`.
- `healthcheck` agregado para Postgres local.
- servicio de app estandarizado como `backend`.
- `backend` sin dependencia obligatoria a Postgres local por defecto.
- `DB_SSL_MODE` agregado en `backend` con default `require`.
- default de `APP_CONFIG_CLASS` en compose a `config.settings.ProductionConfig`.
- removido default productivo `host.docker.internal`.

2. `.env.example`
- bloque explicito para produccion con Supabase (`DB_*`, `DB_SSL_MODE=require`).
- bloque explicito para desarrollo local opcional con `POSTGRES_*` y `DB_HOST=postgres`.
- advertencias para evitar reutilizar usuarios Supabase como `POSTGRES_USER`.

3. Documentacion
- `README.md`: nueva subseccion Docker Compose para produccion (Supabase) vs local (`--profile local-db`), comandos y advertencias operativas.
- `docs/deployment_ubuntu_self_hosted.md`: regla explicita de DB productiva Supabase y uso exclusivo local del profile `local-db`.
- `docs/backend_release_workflow.md`: politica de DB alineada a Supabase en produccion.

## Validaciones ejecutadas
```bash
docker compose config
docker compose config --services
docker compose --profile local-db config --services
python -m py_compile config/settings.py
python -m py_compile api/app.py
```

Resultado observado:
- `docker compose config --services`:
  - `backend`
- `docker compose --profile local-db config --services`:
  - `backend`
  - `postgres`

Interpretacion:
- `postgres` existe como servicio versionado, pero solo se levanta cuando se activa `--profile local-db`.
- flujo productivo no requiere levantar Postgres local.

## Caveats
- `readyz` completo contra Supabase depende de credenciales reales del entorno y conectividad de red del host.
- En este workspace no se expusieron ni versionaron secretos reales.

## Estado final
`final_deployment_config_status=pass`
