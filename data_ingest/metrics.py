from dataclasses import dataclass, field
import time
from typing import List, Optional


@dataclass
class ErrorSample:
    stage: str
    message: str


@dataclass
class IngestStats:
    source: str
    sink: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    records_read: int = 0
    records_written: int = 0
    records_filtered: int = 0
    records_failed: int = 0
    batches_written: int = 0
    error_samples: List[ErrorSample] = field(default_factory=list)
    max_error_samples: int = 10

    def record_error(self, stage: str, exc: Exception) -> None:
        self.records_failed += 1
        if len(self.error_samples) < self.max_error_samples:
            self.error_samples.append(ErrorSample(stage=stage, message=str(exc)))

    def stop(self) -> None:
        self.end_time = time.time()

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return self.end_time - self.start_time
