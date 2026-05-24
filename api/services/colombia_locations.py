from __future__ import annotations

import re
import unicodedata
from typing import Iterable


_COLOMBIA_LOCATIONS: dict[str, tuple[str, ...]] = {
    "Cundinamarca": (
        "Facatativa",
        "Madrid",
        "Mosquera",
        "Funza",
        "Chia",
        "Soacha",
        "Zipaquira",
    ),
    "Bogota D.C.": ("Bogota",),
    "Antioquia": ("Medellin",),
    "Valle del Cauca": ("Cali",),
    "Atlantico": ("Barranquilla",),
    "Santander": ("Bucaramanga",),
    "Bolivar": ("Cartagena",),
    "Boyaca": ("Tunja",),
    "Tolima": ("Ibague",),
    "Meta": ("Villavicencio",),
}

_NORM_DEPARTMENTS = {None: None}
_NORM_CITY_BY_DEPT: dict[str, dict[str, str]] = {}


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


for department, cities in _COLOMBIA_LOCATIONS.items():
    dep_key = _normalize_text(department)
    _NORM_DEPARTMENTS[dep_key] = department
    city_map: dict[str, str] = {}
    for city in cities:
        city_map[_normalize_text(city)] = city
    _NORM_CITY_BY_DEPT[department] = city_map


def catalog_payload() -> dict:
    return {
        "country": "Colombia",
        "departments": [
            {
                "department": department,
                "cities": list(cities),
            }
            for department, cities in _COLOMBIA_LOCATIONS.items()
        ],
    }


def canonical_department(value: str | None) -> str | None:
    if value is None:
        return None
    key = _normalize_text(value)
    if not key:
        return None
    return _NORM_DEPARTMENTS.get(key)


def canonical_city(department: str | None, city: str | None) -> str | None:
    if city is None:
        return None
    city_key = _normalize_text(city)
    if not city_key:
        return None
    canonical_dep = canonical_department(department)
    if not canonical_dep:
        return None
    return _NORM_CITY_BY_DEPT.get(canonical_dep, {}).get(city_key)


def city_belongs_to_department(department: str | None, city: str | None) -> bool:
    if city is None or not str(city).strip():
        return True
    return canonical_city(department, city) is not None


def cities_for_department(department: str | None) -> list[str] | None:
    canonical_dep = canonical_department(department)
    if not canonical_dep:
        return None
    return list(_COLOMBIA_LOCATIONS[canonical_dep])


def parse_city_department_text(raw_value: str | None) -> tuple[str | None, str | None]:
    if raw_value is None:
        return None, None
    raw = str(raw_value).strip()
    if not raw:
        return None, None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if len(parts) >= 2:
        city = canonical_city(parts[-1], parts[0])
        dep = canonical_department(parts[-1])
        if dep and city:
            return dep, city
    norm = _normalize_text(raw)
    dep = _NORM_DEPARTMENTS.get(norm)
    if dep:
        return dep, None
    for canonical_dep, city_map in _NORM_CITY_BY_DEPT.items():
        if norm in city_map:
            return canonical_dep, city_map[norm]
    return None, None


def resolve_department_city(
    *,
    department: str | None,
    city: str | None,
    legacy_department: str | None = None,
    legacy_city: str | None = None,
    legacy_location: str | None = None,
) -> tuple[str | None, str | None]:
    dep = department.strip() if isinstance(department, str) else department
    cty = city.strip() if isinstance(city, str) else city
    dep = dep or None
    cty = cty or None

    if not dep and legacy_department:
        dep = legacy_department.strip() or None
    if not cty and legacy_city:
        cty = legacy_city.strip() or None

    if legacy_location and (not dep or not cty):
        parsed_dep, parsed_city = parse_city_department_text(legacy_location)
        dep = dep or parsed_dep
        cty = cty or parsed_city

    canonical_dep = canonical_department(dep) if dep else None
    if dep and not canonical_dep:
        raise ValueError("invalid_department")

    canonical_cty = canonical_city(canonical_dep, cty) if cty else None
    if cty and not canonical_cty:
        raise ValueError("invalid_city_for_department")

    return canonical_dep, canonical_cty


def infer_department_city_from_text(value: str | None) -> tuple[str | None, str | None]:
    if value is None or not str(value).strip():
        return None, None
    dep, cty = parse_city_department_text(value)
    return dep, cty


def normalized_location_match_tokens(department: str | None, city: str | None) -> tuple[str, str]:
    return _normalize_text(department), _normalize_text(city)


def has_any_location_values(values: Iterable[str | None]) -> bool:
    for value in values:
        if value is not None and str(value).strip():
            return True
    return False
