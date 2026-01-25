"""Assertion helpers for test automation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Assertion:
    operator: str
    expected: Any
    path: str | None = None


def _extract_path(value: Any, path: str | None) -> Any:
    if path is None or path == "":
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise ValueError(f"List index must be int, got: {part}") from exc
            try:
                current = current[index]
            except IndexError as exc:
                raise ValueError(f"List index out of range: {index}") from exc
            continue
        if isinstance(current, dict):
            if part not in current:
                raise ValueError(f"Path '{path}' missing key: {part}")
            current = current[part]
            continue
        raise ValueError(f"Cannot navigate path '{path}' at '{part}'")
    return current


def evaluate_assertion(value: Any, assertion: Assertion) -> tuple[bool, str]:
    actual = _extract_path(value, assertion.path)
    op = assertion.operator
    expected = assertion.expected

    if op == "equals":
        return actual == expected, f"expected {expected!r}, got {actual!r}"
    if op == "not_equals":
        return actual != expected, f"expected not {expected!r}, got {actual!r}"
    if op == "greater_than":
        return actual > expected, f"expected > {expected!r}, got {actual!r}"
    if op == "greater_or_equal":
        return actual >= expected, f"expected >= {expected!r}, got {actual!r}"
    if op == "less_than":
        return actual < expected, f"expected < {expected!r}, got {actual!r}"
    if op == "less_or_equal":
        return actual <= expected, f"expected <= {expected!r}, got {actual!r}"
    if op == "contains":
        return expected in actual, f"expected {actual!r} to contain {expected!r}"
    if op == "starts_with":
        return str(actual).startswith(str(expected)), (
            f"expected {actual!r} to start with {expected!r}"
        )
    if op == "ends_with":
        return str(actual).endswith(str(expected)), (
            f"expected {actual!r} to end with {expected!r}"
        )

    raise ValueError(f"Unsupported assertion operator: {op}")
