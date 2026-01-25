"""CLI runner for AWS test automation."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .assertions import evaluate_assertion
from .aws_clients import AwsClients, AwsConfig
from .config_loader import RunnerConfig, TestDefinition, load_config
from .executors import EXECUTORS


@dataclass
class TestResult:
    name: str
    type: str
    passed: bool
    details: str
    value: Any | None
    error: str | None


def _run_single_test(
    clients: AwsClients, config: RunnerConfig, test: TestDefinition
) -> TestResult:
    executor = EXECUTORS.get(test.type)
    if not executor:
        return TestResult(
            name=test.name,
            type=test.type,
            passed=False,
            details="unsupported test type",
            value=None,
            error=f"Unsupported test type: {test.type}",
        )
    try:
        if test.type == "redshift_sql":
            value = executor(clients, test, config.redshift)
        else:
            value = executor(clients, test)
        passed, details = evaluate_assertion(value, test.assertion)
        return TestResult(
            name=test.name,
            type=test.type,
            passed=passed,
            details=details,
            value=value,
            error=None,
        )
    except Exception as exc:  # pylint: disable=broad-except
        return TestResult(
            name=test.name,
            type=test.type,
            passed=False,
            details="exception during execution",
            value=None,
            error=str(exc),
        )


def run_tests_from_config(
    config: RunnerConfig, fail_fast: bool = False
) -> Dict[str, Any]:
    clients = AwsClients(
        AwsConfig(
            region=config.aws_region,
            role_arn=config.role_arn,
            external_id=config.external_id,
        )
    )

    results: List[TestResult] = []
    for test in config.tests:
        result = _run_single_test(clients, config, test)
        results.append(result)
        if fail_fast and not result.passed:
            break

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "results": [asdict(r) for r in results],
    }


def run_tests(config_path: str, fail_fast: bool = False) -> Dict[str, Any]:
    config = load_config(config_path)
    return run_tests_from_config(config, fail_fast=fail_fast)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AWS test automation.")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--output", help="Optional output JSON file")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    args = parser.parse_args()

    report = run_tests(args.config, fail_fast=args.fail_fast)
    print(json.dumps(report["summary"], indent=2))

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
