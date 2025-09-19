"""Env-driven kafka producer/consumer factory.

Two deploy targets share the same code path:

- Local dev / CI: docker-compose kafka, PLAINTEXT on :9092. Set
  `KAFKA_BOOTSTRAP=kafka:9092` and `KAFKA_SECURITY_PROTOCOL=PLAINTEXT`.
- Prod (MSK on EKS): SASL_SSL with AWS_MSK_IAM mechanism. The pod's IRSA
  role grants `kafka-cluster:{Connect,WriteData,ReadData}`. Set
  `KAFKA_SECURITY_PROTOCOL=SASL_SSL` and `KAFKA_SASL_MECHANISM=AWS_MSK_IAM`.

aiokafka itself is imported lazily inside the build functions so the rest
of the package can be tested without the real client installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

# topic that ingest writes to and the replay consumer reads from
EVENTS_TOPIC = "openproject.events.raw"

# consumer group id used by the replay consumer
CONSUMER_GROUP = "openproject-mcp-replayer"


@dataclass
class KafkaSettings:
    """Resolved kafka client settings derived from environment variables."""

    bootstrap: str
    security_protocol: str
    sasl_mechanism: str
    region: str
    topic: str
    group_id: str

    @classmethod
    def from_env(cls) -> "KafkaSettings":
        sec = os.environ.get("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").upper()
        return cls(
            bootstrap=os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092"),
            security_protocol=sec,
            sasl_mechanism=os.environ.get("KAFKA_SASL_MECHANISM", "").upper(),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            topic=os.environ.get("KAFKA_EVENTS_TOPIC", EVENTS_TOPIC),
            group_id=os.environ.get("KAFKA_CONSUMER_GROUP", CONSUMER_GROUP),
        )

    @property
    def is_msk_iam(self) -> bool:
        """True when env asks for AWS_MSK_IAM SASL auth."""
        return (
            self.security_protocol == "SASL_SSL"
            and self.sasl_mechanism == "AWS_MSK_IAM"
        )


def _common_producer_kwargs(settings: KafkaSettings) -> Dict[str, Any]:
    """Producer kwargs that apply regardless of auth mechanism.

    Idempotence + acks=all + gzip is the durability/throughput sweet spot
    everywhere. compression keeps MSK egress and the S3 mirror cheap.
    """
    return {
        "bootstrap_servers": settings.bootstrap,
        "enable_idempotence": True,
        "acks": "all",
        "compression_type": "gzip",
        "linger_ms": 20,
        "max_in_flight_requests_per_connection": 5,
    }


def _common_consumer_kwargs(settings: KafkaSettings) -> Dict[str, Any]:
    """Consumer kwargs shared by every deploy target.

    Auto-commit is off so the replay consumer commits offsets only after a
    cache write succeeds. Default to latest so a freshly started pod
    doesn't replay the world unless --from-beginning is set.
    """
    return {
        "bootstrap_servers": settings.bootstrap,
        "group_id": settings.group_id,
        "enable_auto_commit": False,
        "auto_offset_reset": "latest",
        "max_poll_records": 500,
    }


def build_producer():  # noqa: ANN201 - returns AIOKafkaProducer when aiokafka present
    """Construct a configured AIOKafkaProducer. Import is deferred."""
    from aiokafka import AIOKafkaProducer  # noqa: WPS433 - lazy import

    settings = KafkaSettings.from_env()
    kwargs = _common_producer_kwargs(settings)
    if settings.is_msk_iam:
        kwargs.update(_msk_iam_auth_kwargs(settings))
    return AIOKafkaProducer(**kwargs)


def _build_msk_iam_token_provider(region: str):  # noqa: ANN201
    """Construct an `aws-msk-iam-sasl-signer-python` callable.

    aiokafka calls the provider on every authentication so it picks up
    token rotation transparently. Raises ImportError if the optional dep
    is missing. Intentionally not soft-failing because silently
    downgrading auth in prod would be a quiet outage.
    """
    from aws_msk_iam_sasl_signer import MSKAuthTokenProvider  # noqa: WPS433

    class _OAuthBearerTokenProvider:
        """aiokafka expects an object with `.token()` returning a string."""

        def __init__(self, region_: str) -> None:
            self._region = region_

        async def token(self) -> str:
            token, _expiry_ms = MSKAuthTokenProvider.generate_auth_token(self._region)
            return token

    return _OAuthBearerTokenProvider(region)


def _msk_iam_auth_kwargs(settings: KafkaSettings) -> Dict[str, Any]:
    """Return the aiokafka kwargs that turn on AWS_MSK_IAM SASL auth.

    The IRSA pod role on EKS grants `kafka-cluster:Connect/WriteData/ReadData`
    on the cluster ARN. The signer reads creds from the standard AWS chain.
    """
    return {
        "security_protocol": settings.security_protocol,
        "sasl_mechanism": "OAUTHBEARER",  # aiokafka's wrapper for IAM tokens
        "sasl_oauth_token_provider": _build_msk_iam_token_provider(settings.region),
    }
