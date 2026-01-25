"""AWS Lambda entry point for executing tests."""
from __future__ import annotations

import json
from typing import Any, Dict

from .config_loader import load_config_from_dict
from .runner import run_tests_from_config


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    if "config" not in event:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'config' in event"}),
        }

    config = load_config_from_dict(event["config"])
    report = run_tests_from_config(config, fail_fast=event.get("fail_fast", False))
    status_code = 200 if report["summary"]["failed"] == 0 else 500
    return {"statusCode": status_code, "body": json.dumps(report)}
