# Python
Python snippets

## Data ingest and processing
The `data_ingest` package provides building blocks for ingest pipelines:

- Sources: CSV, JSON Lines, SQLite, or in-memory records.
- Processors: validation, filtering, mapping, coercion, deduplication.
- Sinks: CSV, JSON Lines, in-memory, or null sinks.
- Pipeline orchestration with batching, metrics, and retry policy.

Example usage:
```
python examples/ingest_csv_to_jsonl.py
```
Update the input/output paths to match your data files.
