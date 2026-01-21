from __future__ import annotations

from collections import deque
from typing import Callable, Hashable, Iterable, Mapping, Optional, Protocol, Sequence

from .errors import ValidationError
from .types import Record


class Processor(Protocol):
    def process(self, record: Record) -> Iterable[Record]:
        """Transform a record and return an iterable of output records."""


class MapProcessor:
    def __init__(self, func: Callable[[Record], Optional[Record]]) -> None:
        self._func = func

    def process(self, record: Record) -> Iterable[Record]:
        result = self._func(record)
        if result is None:
            return []
        return [result]


class FilterProcessor:
    def __init__(self, predicate: Callable[[Record], bool]) -> None:
        self._predicate = predicate

    def process(self, record: Record) -> Iterable[Record]:
        if self._predicate(record):
            return [record]
        return []


class SchemaValidator:
    def __init__(
        self,
        *,
        required_fields: Sequence[str] = (),
        field_types: Optional[Mapping[str, type]] = None,
        allow_extra_fields: bool = True,
    ) -> None:
        self._required_fields = set(required_fields)
        self._field_types = dict(field_types or {})
        self._allow_extra_fields = allow_extra_fields

    def process(self, record: Record) -> Iterable[Record]:
        missing = [field for field in self._required_fields if field not in record]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")
        if not self._allow_extra_fields:
            extra = set(record.keys()) - self._required_fields - set(self._field_types.keys())
            if extra:
                raise ValidationError(f"Unexpected fields: {', '.join(sorted(extra))}")
        for field, expected_type in self._field_types.items():
            if field not in record or record[field] is None:
                continue
            if not isinstance(record[field], expected_type):
                raise ValidationError(
                    f"Field '{field}' expected {expected_type}, got {type(record[field])}"
                )
        return [record]


class TypeCoercionProcessor:
    def __init__(
        self,
        field_transforms: Mapping[str, Callable[[object], object]],
        *,
        allow_missing: bool = True,
    ) -> None:
        self._field_transforms = dict(field_transforms)
        self._allow_missing = allow_missing

    def process(self, record: Record) -> Iterable[Record]:
        updated = dict(record)
        for field, transform in self._field_transforms.items():
            if field not in updated:
                if self._allow_missing:
                    continue
                raise ValidationError(f"Missing field '{field}' for coercion")
            if updated[field] is None:
                continue
            try:
                updated[field] = transform(updated[field])
            except Exception as exc:
                raise ValidationError(f"Failed to coerce field '{field}'") from exc
        return [updated]


class DeduplicateProcessor:
    def __init__(
        self,
        key_fn: Callable[[Record], Hashable],
        *,
        max_entries: Optional[int] = None,
    ) -> None:
        self._key_fn = key_fn
        self._max_entries = max_entries
        self._seen = set()
        self._order = deque()

    def process(self, record: Record) -> Iterable[Record]:
        key = self._key_fn(record)
        if key in self._seen:
            return []
        self._seen.add(key)
        if self._max_entries is not None:
            self._order.append(key)
            if len(self._order) > self._max_entries:
                evicted = self._order.popleft()
                self._seen.discard(evicted)
        return [record]
