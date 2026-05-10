import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from api.app import create_app
from config.settings import TestingConfig


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
IGNORED_RUNTIME_PATHS = {"/static/{path}"}


def _to_openapi_style(path: str) -> str:
    # Flask params: <id> or <uuid:id> -> OpenAPI: {id}
    normalized = path
    normalized = normalized.replace("<string:", "<")
    normalized = normalized.replace("<int:", "<")
    normalized = normalized.replace("<uuid:", "<")
    while "<" in normalized and ">" in normalized:
        start = normalized.index("<")
        end = normalized.index(">", start)
        name = normalized[start + 1 : end].split(":")[-1]
        normalized = normalized[:start] + "{" + name + "}" + normalized[end + 1 :]
    return normalized


def _canonical_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def _read_spec_paths(spec_path: Path) -> dict[str, set[str]]:
    text = spec_path.read_text(encoding="utf-8").splitlines()
    in_paths = False
    current_path = None
    parsed: dict[str, set[str]] = defaultdict(set)

    for line in text:
        if not in_paths:
            if line.strip() == "paths:":
                in_paths = True
            continue

        if re.match(r"^[^\s]", line):
            break

        match_path = re.match(r"^  (/[^:]+):\s*$", line)
        if match_path:
            current_path = match_path.group(1).strip()
            continue

        match_method = re.match(r"^    ([a-z]+):\s*$", line)
        if match_method and current_path:
            method = match_method.group(1).lower()
            if method in HTTP_METHODS:
                parsed[_canonical_path(current_path)].add(method)

    return parsed


def _runtime_paths(app) -> dict[str, set[str]]:
    parsed: dict[str, set[str]] = defaultdict(set)
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = _to_openapi_style(rule.rule)
        if path in IGNORED_RUNTIME_PATHS:
            continue
        canonical = _canonical_path(path)
        for method in rule.methods:
            method_l = method.lower()
            if method_l in HTTP_METHODS:
                parsed[canonical].add(method_l)
    return parsed


def test_openapi_matches_registered_runtime_routes():
    app = create_app(TestingConfig)
    runtime = _runtime_paths(app)
    spec = _read_spec_paths(Path(PROJECT_ROOT) / "docs" / "openapi.yaml")

    missing_in_spec = []
    method_mismatches = []
    extra_in_spec = []

    for path, runtime_methods in sorted(runtime.items()):
        spec_methods = spec.get(path)
        if not spec_methods:
            missing_in_spec.append((path, sorted(runtime_methods)))
            continue
        missing_methods = sorted(runtime_methods - spec_methods)
        if missing_methods:
            method_mismatches.append((path, missing_methods, sorted(spec_methods)))

    for path, spec_methods in sorted(spec.items()):
        runtime_methods = runtime.get(path)
        if not runtime_methods:
            extra_in_spec.append((path, sorted(spec_methods)))

    assert not missing_in_spec, f"Runtime paths missing in OpenAPI: {missing_in_spec}"
    assert not method_mismatches, f"Runtime method mismatches in OpenAPI: {method_mismatches}"
    assert not extra_in_spec, f"OpenAPI paths not mounted at runtime: {extra_in_spec}"
