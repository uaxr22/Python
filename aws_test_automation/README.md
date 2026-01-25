# AWS Test Automation (SQL + Python + AWS)

This package provides a small, working test automation runner that uses
SQL (Redshift + DynamoDB PartiQL), Python, and AWS services (Lambda, Glue,
Redshift, DynamoDB). It is designed for both local execution and Lambda.

## What it does

- Executes SQL checks in Redshift via the Redshift Data API.
- Executes PartiQL checks in DynamoDB.
- Invokes Lambda functions and validates responses.
- Validates Glue job runs (latest or newly started).

## Quick start (local)

1. Ensure AWS credentials are available (env vars or ~/.aws/credentials).
2. Install boto3 if needed:
   - `pip install boto3`
3. Run:

```bash
python -m aws_test_automation.runner --config aws_test_automation/config/sample_tests.json
```

Optional output file:

```bash
python -m aws_test_automation.runner \
  --config aws_test_automation/config/sample_tests.json \
  --output /tmp/test_report.json
```

## Lambda usage

Deploy `aws_test_automation/lambda_handler.py` as the Lambda handler.
Invoke with:

```json
{
  "fail_fast": false,
  "config": {
    "aws_region": "us-east-1",
    "redshift": {
      "cluster_identifier": "your-redshift-cluster",
      "database": "dev",
      "db_user": "awsuser"
    },
    "tests": [
      {
        "name": "row_count",
        "type": "redshift_sql",
        "sql": "SELECT COUNT(*) FROM public.orders",
        "assertion": {"operator": "greater_than", "expected": 0}
      }
    ]
  }
}
```

## Config reference

Top-level:

- `aws_region`: AWS region (default `us-east-1`)
- `role_arn` / `external_id`: optional role assumption
- `redshift`: optional Redshift config
- `tests`: list of test definitions

Redshift config:

- `database` (required)
- `cluster_identifier` or `workgroup_name`
- `db_user` (required for cluster auth)
- `secret_arn` (optional for Secrets Manager auth)

Test types:

- `redshift_sql`: use `sql` or `sql_file`
- `dynamodb_partiql`: use `statement` or `statement_file`
- `lambda_invoke`: use `function_name`, optional `payload`
- `glue_job_status`: use `job_name`, optional `start_new_run`

Assertions:

```
{
  "operator": "equals|not_equals|greater_than|greater_or_equal|less_than|less_or_equal|contains|starts_with|ends_with",
  "expected": <value>,
  "path": "optional.dot.path"
}
```

## IAM permissions

You will need permissions for the services you use:

- `redshift-data:ExecuteStatement`, `redshift-data:GetStatementResult`,
  `redshift-data:DescribeStatement`
- `dynamodb:ExecuteStatement`
- `lambda:InvokeFunction`
- `glue:GetJobRuns`, `glue:GetJobRun`, `glue:StartJobRun`

## Notes

- SQL files in `aws_test_automation/sql/` can be referenced with `sql_file`.
- PartiQL files can be referenced with `statement_file`.
