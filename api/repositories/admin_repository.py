from __future__ import annotations

from typing import Iterable

from sqlalchemy import asc, desc


def apply_pagination(query, *, page: int, page_size: int):
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 20), 1), 100)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, {
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


def apply_sort(query, *, model, sort: str | None, order: str | None, allowed: Iterable[str]):
    if not sort or sort not in allowed:
        return query
    column = getattr(model, sort, None)
    if column is None:
        return query
    direction = (order or "desc").lower()
    if direction == "asc":
        return query.order_by(asc(column))
    return query.order_by(desc(column))
