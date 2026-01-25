"""Test executors for AWS services."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from .aws_clients import AwsClients
from .config_loader import RedshiftConfig, TestDefinition


def _redshift_field_to_python(field: Dict[str, Any]) -> Any:
    if "isNull" in field and field["isNull"]:
        return None
    for key in ("stringValue", "longValue", "doubleValue", "booleanValue"):
        if key in field:
            return field[key]
    return field


def _normalize_redshift_records(records: List[List[Dict[str, Any]]]) -> Any:
    rows = [[_redshift_field_to_python(cell) for cell in row] for row in records]
    if len(rows) == 1 and len(rows[0]) == 1:
        return rows[0][0]
    return rows


def _wait_for_redshift_statement(
    client, statement_id: str, timeout_seconds: int = 120
) -> Dict[str, Any]:
    start = time.time()
    while True:
        status = client.describe_statement(Id=statement_id)
        if status["Status"] in {"FINISHED", "FAILED", "ABORTED"}:
            return status
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Redshift statement timed out: {statement_id}")
        time.sleep(1.5)


def _load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def execute_redshift_sql(
    clients: AwsClients, test: TestDefinition, redshift: RedshiftConfig | None
) -> Any:
    if not redshift:
        raise ValueError("Redshift config is required for redshift_sql tests")
    if "sql" in test.config:
        sql = test.config["sql"]
    elif "sql_file" in test.config:
        sql = _load_text(test.config["sql_file"])
    else:
        raise ValueError("redshift_sql requires 'sql' or 'sql_file'")
    statement_args = redshift.statement_args()
    statement_args["Sql"] = sql
    client = clients.redshift_data()
    response = client.execute_statement(**statement_args)
    status = _wait_for_redshift_statement(
        client, response["Id"], timeout_seconds=test.config.get("timeout_seconds", 120)
    )
    if status["Status"] != "FINISHED":
        raise RuntimeError(
            f"Redshift statement failed: {status.get('Error') or status['Status']}"
        )
    result = client.get_statement_result(Id=response["Id"])
    return _normalize_redshift_records(result.get("Records", []))


def execute_dynamodb_partiql(clients: AwsClients, test: TestDefinition) -> Dict[str, Any]:
    client = clients.dynamodb()
    params = test.config.get("parameters") or []
    if "statement" in test.config:
        statement = test.config["statement"]
    elif "statement_file" in test.config:
        statement = _load_text(test.config["statement_file"])
    else:
        raise ValueError("dynamodb_partiql requires 'statement' or 'statement_file'")
    response = client.execute_statement(Statement=statement, Parameters=params)
    return {
        "Items": response.get("Items", []),
        "Count": response.get("Count"),
        "ScannedCount": response.get("ScannedCount"),
    }


def execute_lambda_invoke(clients: AwsClients, test: TestDefinition) -> Dict[str, Any]:
    client = clients.lambda_()
    payload = test.config.get("payload")
    if payload is None:
        encoded_payload = b"{}"
    elif isinstance(payload, (dict, list)):
        encoded_payload = json.dumps(payload).encode("utf-8")
    elif isinstance(payload, str):
        encoded_payload = payload.encode("utf-8")
    else:
        raise ValueError("Lambda payload must be dict, list, or string")

    response = client.invoke(
        FunctionName=test.config["function_name"],
        InvocationType=test.config.get("invocation_type", "RequestResponse"),
        Payload=encoded_payload,
    )
    raw_payload = response["Payload"].read().decode("utf-8")
    try:
        parsed_payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        parsed_payload = raw_payload
    return {
        "StatusCode": response.get("StatusCode"),
        "FunctionError": response.get("FunctionError"),
        "Payload": parsed_payload,
    }


def _wait_for_glue_job(
    client, job_name: str, run_id: str, timeout_seconds: int
) -> Dict[str, Any]:
    start = time.time()
    while True:
        response = client.get_job_run(JobName=job_name, RunId=run_id)
        job_run = response["JobRun"]
        if job_run["JobRunState"] in {"SUCCEEDED", "FAILED", "STOPPED", "TIMEOUT"}:
            return job_run
        if time.time() - start > timeout_seconds:
            raise TimeoutError(f"Glue job timed out: {job_name} ({run_id})")
        time.sleep(5)


def execute_glue_job_status(clients: AwsClients, test: TestDefinition) -> Dict[str, Any]:
    client = clients.glue()
    job_name = test.config["job_name"]
    if test.config.get("start_new_run"):
        start_response = client.start_job_run(JobName=job_name)
        run_id = start_response["JobRunId"]
        job_run = _wait_for_glue_job(
            client,
            job_name,
            run_id,
            timeout_seconds=test.config.get("timeout_seconds", 900),
        )
        return job_run

    if "run_id" in test.config:
        response = client.get_job_run(
            JobName=job_name, RunId=test.config["run_id"]
        )
        return response["JobRun"]

    response = client.get_job_runs(JobName=job_name, MaxResults=1)
    runs = response.get("JobRuns", [])
    if not runs:
        raise RuntimeError(f"No Glue job runs found for: {job_name}")
    return runs[0]


EXECUTORS = {
    "redshift_sql": execute_redshift_sql,
    "dynamodb_partiql": execute_dynamodb_partiql,
    "lambda_invoke": execute_lambda_invoke,
    "glue_job_status": execute_glue_job_status,
}
