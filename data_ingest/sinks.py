from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Sequence

from .errors import SinkError
from .types import Record
from .utils import default_json_serializer, ensure_parent_dir


class Sink(Protocol):
    def write(self, records: Sequence[Record]) -> int:
        """Write a batch of records and return the count written."""

    def close(self) -> None:
        """Release any resources held by the sink."""


class BaseSink:
    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name or self.__class__.__name__

    def close(self) -> None:
        return None


class JsonLinesSink(BaseSink):
    def __init__(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        append: bool = False,
        ensure_ascii: bool = True,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.path = Path(path)
        self.encoding = encoding
        self.append = append
        self.ensure_ascii = ensure_ascii
        self._handle = None

    def _open(self) -> None:
        if self._handle is None:
            ensure_parent_dir(self.path)
            mode = "a" if self.append else "w"
            self._handle = self.path.open(mode, encoding=self.encoding)

    def write(self, records: Sequence[Record]) -> int:
        if not records:
            return 0
        self._open()
        if self._handle is None:
            raise SinkError("Failed to open JSONL sink")
        try:
            for record in records:
                payload = json.dumps(
                    record,
                    default=default_json_serializer,
                    ensure_ascii=self.ensure_ascii,
                )
                self._handle.write(payload + "\n")
        except Exception as exc:
            raise SinkError("Failed to write JSONL records") from exc
        return len(records)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


class CsvSink(BaseSink):
    def __init__(
        self,
        path: str,
        *,
        fieldnames: Optional[Sequence[str]] = None,
        encoding: str = "utf-8",
        append: bool = False,
        extras_action: str = "raise",
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.path = Path(path)
        self.fieldnames = list(fieldnames) if fieldnames else None
        self.encoding = encoding
        self.append = append
        self.extras_action = extras_action
        self._handle = None
        self._writer = None
        if self.append and self.fieldnames is None and self.path.exists():
            raise SinkError(
                "fieldnames must be set when appending to an existing CSV"
            )

    def _open(self, records: Sequence[Record]) -> None:
        if self._handle is not None:
            return
        if self.fieldnames is None:
            if not records:
                return
            self.fieldnames = list(records[0].keys())
        ensure_parent_dir(self.path)
        mode = "a" if self.append else "w"
        self._handle = self.path.open(mode, encoding=self.encoding, newline="")
        self._writer = csv.DictWriter(
            self._handle,
            fieldnames=self.fieldnames,
            extrasaction=self.extras_action,
        )
        if not self.append:
            self._writer.writeheader()

    def write(self, records: Sequence[Record]) -> int:
        if not records:
            return 0
        self._open(records)
        if self._writer is None:
            raise SinkError("Failed to open CSV sink")
        for record in records:
            if self.fieldnames is None:
                raise SinkError("CSV fieldnames are not set")
            try:
                self._writer.writerow(record)
            except ValueError as exc:
                raise SinkError("Failed to write CSV record") from exc
        return len(records)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
            self._writer = None


class InMemorySink(BaseSink):
    def __init__(self, name: Optional[str] = None) -> None:
        super().__init__(name=name)
        self.records: List[Record] = []

    def write(self, records: Sequence[Record]) -> int:
        self.records.extend(records)
        return len(records)


class NullSink(BaseSink):
    def write(self, records: Sequence[Record]) -> int:
        return len(records)
