"""Config loading for AWS test automation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
from pathlib import Path

from .assertions import Assertion


@dataclass(frozen=True)
class RedshiftConfig:
    database: str
    cluster_identifier: str | None = None
    workgroup_name: str | None = None
    db_user: str | None = None
    secret_arn: str | None = None

    def statement_args(self) -> Dict[str, Any]:
        args: Dict[str, Any] = {"Database": self.database}
        if self.cluster_identifier:
            args["ClusterIdentifier"] = self.cluster_identifier
        if self.workgroup_name:
            args["WorkgroupName"] = self.workgroup_name
        if self.db_user:
            args["DbUser"] = self.db_user
        if self.secret_arn:
            args["SecretArn"] = self.secret_arn
        return args


@dataclass(frozen=True)
class TestDefinition:
    name: str
    type: str
    config: Dict[str, Any]
    assertion: Assertion


@dataclass(frozen=True)
class RunnerConfig:
    aws_region: str
    role_arn: str | None
    external_id: str | None
    redshift: RedshiftConfig | None
    tests: List[TestDefinition]


def _parse_assertion(data: Dict[str, Any]) -> Assertion:
    return Assertion(
        operator=data["operator"],
        expected=data.get("expected"),
        path=data.get("path"),
    )


def load_config(path: str | Path) -> RunnerConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return load_config_from_dict(raw)


def load_config_from_dict(raw: Dict[str, Any]) -> RunnerConfig:
    redshift_cfg = None
    if "redshift" in raw:
        redshift_cfg = RedshiftConfig(
            database=raw["redshift"]["database"],
            cluster_identifier=raw["redshift"].get("cluster_identifier"),
            workgroup_name=raw["redshift"].get("workgroup_name"),
            db_user=raw["redshift"].get("db_user"),
            secret_arn=raw["redshift"].get("secret_arn"),
        )
    tests = []
    for test in raw.get("tests", []):
        if "assertion" not in test:
            raise ValueError(f"Test {test.get('name')} missing assertion")
        assertion = _parse_assertion(test["assertion"])
        config = {k: v for k, v in test.items() if k not in {"name", "type", "assertion"}}
        tests.append(
            TestDefinition(
                name=test["name"],
                type=test["type"],
                config=config,
                assertion=assertion,
            )
        )

    return RunnerConfig(
        aws_region=raw.get("aws_region", "us-east-1"),
        role_arn=raw.get("role_arn"),
        external_id=raw.get("external_id"),
        redshift=redshift_cfg,
        tests=tests,
    )
