from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Iterator, Optional, Protocol, Sequence

from .errors import SourceError
from .types import Record, RecordMapping


class Source(Protocol):
    def read(self) -> Iterable[Record]:
        """Return an iterable of records."""


class BaseSource:
    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name or self.__class__.__name__


class IterableSource(BaseSource):
    def __init__(self, records: Iterable[RecordMapping], name: Optional[str] = None) -> None:
        super().__init__(name=name)
        self._records = records

    def read(self) -> Iterable[Record]:
        for record in self._records:
            if not isinstance(record, dict):
                record = dict(record)
            yield record


class CsvSource(BaseSource):
    def __init__(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        delimiter: str = ",",
        quotechar: str = '"',
        has_header: bool = True,
        fieldnames: Optional[Sequence[str]] = None,
        skip_initial_space: bool = True,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.path = Path(path)
        self.encoding = encoding
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.has_header = has_header
        self.fieldnames = list(fieldnames) if fieldnames else None
        self.skip_initial_space = skip_initial_space

    def read(self) -> Iterable[Record]:
        if not self.path.exists():
            raise SourceError(f"CSV source not found: {self.path}")
        with self.path.open("r", encoding=self.encoding, newline="") as handle:
            if self.has_header:
                reader = csv.DictReader(
                    handle,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                    skipinitialspace=self.skip_initial_space,
                )
            else:
                if not self.fieldnames:
                    raise SourceError("fieldnames must be set when has_header is False")
                reader = csv.DictReader(
                    handle,
                    fieldnames=self.fieldnames,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                    skipinitialspace=self.skip_initial_space,
                )

            for row in reader:
                if row is None:
                    continue
                if None in row:
                    raise SourceError("CSV row has more columns than expected")
                yield dict(row)


class JsonLinesSource(BaseSource):
    def __init__(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        allow_non_dict: bool = False,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.path = Path(path)
        self.encoding = encoding
        self.allow_non_dict = allow_non_dict

    def read(self) -> Iterable[Record]:
        if not self.path.exists():
            raise SourceError(f"JSONL source not found: {self.path}")
        with self.path.open("r", encoding=self.encoding) as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise SourceError(
                        f"Invalid JSON on line {line_number} of {self.path}"
                    ) from exc
                if isinstance(payload, dict):
                    yield payload
                elif self.allow_non_dict:
                    yield {"value": payload}
                else:
                    raise SourceError(
                        f"Expected JSON object on line {line_number} of {self.path}"
                    )


class SQLiteSource(BaseSource):
    def __init__(
        self,
        db_path: str,
        query: str,
        *,
        params: Optional[Sequence[object]] = None,
        batch_size: int = 1000,
        name: Optional[str] = None,
    ) -> None:
        super().__init__(name=name)
        self.db_path = Path(db_path)
        self.query = query
        self.params = params or []
        self.batch_size = batch_size

    def read(self) -> Iterable[Record]:
        if not self.db_path.exists():
            raise SourceError(f"SQLite database not found: {self.db_path}")
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(self.query, self.params)
            while True:
                rows = cursor.fetchmany(self.batch_size)
                if not rows:
                    break
                for row in rows:
                    yield dict(row)
        except sqlite3.Error as exc:
            raise SourceError("SQLite query failed") from exc
        finally:
            connection.close()
