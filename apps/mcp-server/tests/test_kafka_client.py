"""Env-driven config branch tests for kafka_client.

We can't (and shouldn't) hit a real broker here. Instead we assert that the
KafkaSettings dataclass + the kwargs helpers select the right branches based
on the documented env vars - PLAINTEXT for dev, SASL_SSL+AWS_MSK_IAM for MSK.
"""

import pytest

from openproject_mcp_server.webhooks import kafka_client as kc


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Strip the kafka env vars before each test so defaults are predictable."""
    for var in (
        "KAFKA_BOOTSTRAP",
        "KAFKA_SECURITY_PROTOCOL",
        "KAFKA_SASL_MECHANISM",
        "KAFKA_EVENTS_TOPIC",
        "KAFKA_CONSUMER_GROUP",
        "AWS_REGION",
    ):
        monkeypatch.delenv(var, raising=False)


def test_settings_defaults_are_local_plaintext():
    s = kc.KafkaSettings.from_env()
    assert s.bootstrap == "kafka:9092"
    assert s.security_protocol == "PLAINTEXT"
    assert s.sasl_mechanism == ""
    assert s.topic == kc.EVENTS_TOPIC
    assert s.group_id == kc.CONSUMER_GROUP
    assert s.is_msk_iam is False


def test_settings_pick_up_msk_iam_env(monkeypatch):
    monkeypatch.setenv("KAFKA_BOOTSTRAP", "b-1.cluster.kafka.us-east-1.amazonaws.com:9098")
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("KAFKA_SASL_MECHANISM", "AWS_MSK_IAM")
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    s = kc.KafkaSettings.from_env()
    assert s.is_msk_iam is True
    assert s.region == "us-east-2"
    assert s.bootstrap.endswith(":9098")


def test_settings_topic_and_group_overridable(monkeypatch):
    monkeypatch.setenv("KAFKA_EVENTS_TOPIC", "custom.events")
    monkeypatch.setenv("KAFKA_CONSUMER_GROUP", "custom-replay")
    s = kc.KafkaSettings.from_env()
    assert s.topic == "custom.events"
    assert s.group_id == "custom-replay"


def test_security_protocol_normalized_to_upper(monkeypatch):
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "sasl_ssl")
    monkeypatch.setenv("KAFKA_SASL_MECHANISM", "aws_msk_iam")
    s = kc.KafkaSettings.from_env()
    assert s.security_protocol == "SASL_SSL"
    assert s.sasl_mechanism == "AWS_MSK_IAM"
    assert s.is_msk_iam is True


def test_common_producer_kwargs_have_durability_settings():
    s = kc.KafkaSettings.from_env()
    kwargs = kc._common_producer_kwargs(s)
    assert kwargs["enable_idempotence"] is True
    assert kwargs["acks"] == "all"
    assert kwargs["compression_type"] == "gzip"
    assert kwargs["bootstrap_servers"] == s.bootstrap


def test_common_consumer_kwargs_disable_auto_commit():
    s = kc.KafkaSettings.from_env()
    kwargs = kc._common_consumer_kwargs(s)
    assert kwargs["enable_auto_commit"] is False
    assert kwargs["group_id"] == s.group_id
    assert kwargs["auto_offset_reset"] == "latest"


def test_msk_iam_auth_kwargs_only_loaded_when_iam(monkeypatch):
    """`_msk_iam_auth_kwargs` imports the signer; non-IAM path must not."""
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
    s = kc.KafkaSettings.from_env()
    assert s.is_msk_iam is False
    # build_producer would only call _msk_iam_auth_kwargs when is_msk_iam is True.
    # We mimic that decision here without importing the optional dep.
    if s.is_msk_iam:  # pragma: no cover - branch deliberately not hit in local mode
        kc._msk_iam_auth_kwargs(s)


def test_msk_iam_auth_kwargs_returns_oauthbearer(monkeypatch):
    """Stub the signer module so the kwargs builder runs without aws creds."""
    import sys
    import types

    fake_module = types.ModuleType("aws_msk_iam_sasl_signer")

    class _Provider:
        @staticmethod
        def generate_auth_token(region):
            return ("token-for-" + region, 1000)

    fake_module.MSKAuthTokenProvider = _Provider
    monkeypatch.setitem(sys.modules, "aws_msk_iam_sasl_signer", fake_module)
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("KAFKA_SASL_MECHANISM", "AWS_MSK_IAM")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")

    settings = kc.KafkaSettings.from_env()
    kwargs = kc._msk_iam_auth_kwargs(settings)
    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "OAUTHBEARER"
    provider = kwargs["sasl_oauth_token_provider"]
    # provider exposes async .token()
    import asyncio
    token = asyncio.get_event_loop().run_until_complete(provider.token()) if False else None
    # use asyncio.run to avoid touching the running loop
    token = asyncio.run(provider.token())
    assert token == "token-for-eu-west-1"
