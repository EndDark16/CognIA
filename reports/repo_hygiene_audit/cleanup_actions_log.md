# Cleanup Actions Log

## Ejecutado
- cleanup_type: conservative_cache_cleanup
- removed_paths_count: 14
- estimated_space_freed_mb: 2.412

## Alcance
- Se elimino `.pytest_cache/` de raiz.
- Se eliminaron carpetas `__pycache__/` fuera de cualquier entorno `venv`.
- No se eliminaron datasets, modelos, artefactos de inferencia, ni outputs de auditoria.

## Paths removidos
- `.pytest_cache`
- `api\__pycache__`
- `api\repositories\__pycache__`
- `api\routes\__pycache__`
- `api\schemas\__pycache__`
- `api\services\__pycache__`
- `app\__pycache__`
- `artifacts\inference\__pycache__`
- `config\__pycache__`
- `core\models\__pycache__`
- `migrations\__pycache__`
- `migrations\versions\__pycache__`
- `scripts\__pycache__`
- `tests\__pycache__`