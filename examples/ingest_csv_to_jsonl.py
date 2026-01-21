from data_ingest import (
    CsvSource,
    DataPipeline,
    FilterProcessor,
    JsonLinesSink,
    MapProcessor,
    SchemaValidator,
    TypeCoercionProcessor,
)


def normalize_user(record):
    return {
        "user_id": record["user_id"],
        "email": record["email"].strip().lower(),
        "is_active": record["is_active"],
    }


def main() -> None:
    source = CsvSource("input/users.csv")
    processors = [
        SchemaValidator(
            required_fields=("user_id", "email", "is_active"),
            field_types={"user_id": int, "email": str, "is_active": str},
        ),
        TypeCoercionProcessor({"user_id": int}),
        FilterProcessor(lambda r: r["is_active"].lower() == "true"),
        MapProcessor(normalize_user),
    ]
    sink = JsonLinesSink("output/active_users.jsonl")
    pipeline = DataPipeline(source, sink, processors=processors, batch_size=1000)
    stats = pipeline.run()
    print(
        f"Read {stats.records_read} records, wrote {stats.records_written} "
        f"in {stats.duration_seconds:.2f}s"
    )


if __name__ == "__main__":
    main()
