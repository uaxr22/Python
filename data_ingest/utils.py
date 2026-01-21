from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator, List


def chunked(items: Iterable[Any], size: int) -> Iterator[List[Any]]:
    """Yield lists of up to size items from an iterable."""
    if size <= 0:
        raise ValueError("size must be greater than zero")
    batch: List[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def default_json_serializer(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
