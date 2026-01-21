from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .errors import IngestError, ProcessorError, SinkError, SourceError, TransientError
from .metrics import IngestStats
from .processors import Processor
from .sinks import Sink
from .sources import Source
from .types import Record, RecordMapping


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    retry_exceptions: tuple = (TransientError,)

    def run(self, func, *args, **kwargs):
        attempt = 1
        delay = self.backoff_seconds
        while True:
            try:
                return func(*args, **kwargs)
            except self.retry_exceptions:
                if attempt >= self.max_attempts:
                    raise
                time.sleep(delay)
                attempt += 1
                delay *= self.backoff_multiplier


class DataPipeline:
    def __init__(
        self,
        source: Source,
        sink: Sink,
        *,
        processors: Optional[Sequence[Processor]] = None,
        batch_size: int = 500,
        max_errors: Optional[int] = 0,
        retry_policy: Optional[RetryPolicy] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        self.source = source
        self.sink = sink
        self.processors = list(processors or [])
        self.batch_size = batch_size
        self.max_errors = max_errors
        self.retry_policy = retry_policy
        self.logger = logger or logging.getLogger(__name__)

    def run(self) -> IngestStats:
        stats = IngestStats(
            source=getattr(self.source, "name", self.source.__class__.__name__),
            sink=getattr(self.sink, "name", self.sink.__class__.__name__),
        )
        batch: List[Record] = []
        try:
            for record in self.source.read():
                stats.records_read += 1
                try:
                    processed = self._process_record(record)
                except Exception as exc:
                    self._record_error(stats, "process", exc)
                    if self._should_abort(stats):
                        raise
                    continue
                if not processed:
                    stats.records_filtered += 1
                    continue
                for output in processed:
                    batch.append(output)
                    if len(batch) >= self.batch_size:
                        self._flush_batch(batch, stats)
                        batch = []
            if batch:
                self._flush_batch(batch, stats)
        except SourceError as exc:
            self._record_error(stats, "source", exc)
            raise
        finally:
            try:
                self.sink.close()
            finally:
                stats.stop()
        return stats

    def _normalize_record(self, record: RecordMapping) -> Record:
        if not isinstance(record, dict):
            return dict(record)
        return record

    def _process_record(self, record: RecordMapping) -> List[Record]:
        records: List[Record] = [self._normalize_record(record)]
        for processor in self.processors:
            next_records: List[Record] = []
            for item in records:
                try:
                    processed = processor.process(item)
                except Exception as exc:
                    raise ProcessorError(
                        f"Processor {processor.__class__.__name__} failed"
                    ) from exc
                if processed is None:
                    continue
                for output in processed:
                    if output is None:
                        continue
                    if not isinstance(output, dict):
                        output = dict(output)
                    next_records.append(output)
            records = next_records
            if not records:
                break
        return records

    def _write_batch(self, batch: Sequence[Record], stats: IngestStats) -> None:
        def write_once() -> int:
            return self.sink.write(batch)

        try:
            if self.retry_policy:
                written = self.retry_policy.run(write_once)
            else:
                written = write_once()
            stats.records_written += written
            stats.batches_written += 1
        except Exception as exc:
            raise SinkError("Failed to write batch") from exc

    def _flush_batch(self, batch: Sequence[Record], stats: IngestStats) -> None:
        try:
            self._write_batch(batch, stats)
        except Exception as exc:
            self._record_error(stats, "sink", exc)
            if self._should_abort(stats):
                raise

    def _record_error(self, stats: IngestStats, stage: str, exc: Exception) -> None:
        self.logger.exception("Error in %s stage: %s", stage, exc)
        if not isinstance(exc, IngestError):
            exc = IngestError(str(exc))
        stats.record_error(stage, exc)

    def _should_abort(self, stats: IngestStats) -> bool:
        if self.max_errors is None:
            return False
        return stats.records_failed > self.max_errors
