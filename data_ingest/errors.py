class IngestError(Exception):
    """Base error for ingest and processing failures."""


class SourceError(IngestError):
    """Raised when a source cannot read data."""


class ProcessorError(IngestError):
    """Raised when a processor fails to transform a record."""


class SinkError(IngestError):
    """Raised when a sink cannot write data."""


class ValidationError(ProcessorError):
    """Raised when a record fails validation."""


class TransientError(IngestError):
    """Raised for retriable failures, such as intermittent I/O."""
