"""AWS client factory with optional role assumption."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

try:
    import boto3
except ImportError as exc:  # pragma: no cover - required in runtime environments
    raise RuntimeError(
        "boto3 is required. Install with: pip install boto3"
    ) from exc


@dataclass(frozen=True)
class AwsConfig:
    region: str
    role_arn: str | None = None
    session_name: str = "aws-test-automation"
    external_id: str | None = None


class AwsClients:
    def __init__(self, config: AwsConfig):
        self._config = config
        self._session = self._build_session()

    def _build_session(self) -> boto3.Session:
        if not self._config.role_arn:
            return boto3.Session(region_name=self._config.region)

        sts = boto3.client("sts", region_name=self._config.region)
        assume_args: Dict[str, Any] = {
            "RoleArn": self._config.role_arn,
            "RoleSessionName": self._config.session_name,
        }
        if self._config.external_id:
            assume_args["ExternalId"] = self._config.external_id
        response = sts.assume_role(**assume_args)
        creds = response["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=self._config.region,
        )

    def redshift_data(self):
        return self._session.client("redshift-data")

    def dynamodb(self):
        return self._session.client("dynamodb")

    def lambda_(self):
        return self._session.client("lambda")

    def glue(self):
        return self._session.client("glue")
