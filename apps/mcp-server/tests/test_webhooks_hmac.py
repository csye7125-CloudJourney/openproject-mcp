"""Tests for the webhook HMAC validator.

Covers: good sig accepted, bad sig rejected, missing header rejected,
empty secret fails closed, sha256= prefix handled, body tampering detected.
"""

import hashlib
import hmac

import pytest

from openproject_mcp_server.webhooks.hmac_validator import (
    InvalidSignature,
    compute_signature,
    verify_signature,
)


SECRET = "test-secret-keep-me-out-of-git"


def _sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_compute_signature_matches_manual_hmac():
    body = b'{"project_id":"42"}'
    assert compute_signature(body, secret=SECRET) == _sign(body)


def test_verify_signature_accepts_good_signature():
    body = b'{"hello":"world"}'
    sig = _sign(body)
    # no raise == pass
    verify_signature(body, sig, secret=SECRET)


def test_verify_signature_accepts_sha256_prefix():
    body = b'{"hello":"world"}'
    sig = "sha256=" + _sign(body)
    verify_signature(body, sig, secret=SECRET)


def test_verify_signature_rejects_bad_signature():
    body = b'{"x":1}'
    with pytest.raises(InvalidSignature):
        verify_signature(body, "deadbeef" * 8, secret=SECRET)


def test_verify_signature_rejects_missing_header():
    with pytest.raises(InvalidSignature):
        verify_signature(b"anything", None, secret=SECRET)


def test_verify_signature_rejects_empty_header():
    with pytest.raises(InvalidSignature):
        verify_signature(b"anything", "", secret=SECRET)


def test_verify_signature_detects_body_tampering():
    body = b'{"amount":10}'
    sig = _sign(body)
    tampered = b'{"amount":1000}'
    with pytest.raises(InvalidSignature):
        verify_signature(tampered, sig, secret=SECRET)


def test_empty_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("WEBHOOK_HMAC_SECRET", raising=False)
    with pytest.raises(InvalidSignature):
        # no explicit secret + no env var means no secret at all
        compute_signature(b"body")


def test_env_secret_used_when_no_explicit(monkeypatch):
    monkeypatch.setenv("WEBHOOK_HMAC_SECRET", SECRET)
    body = b'{"k":"v"}'
    assert compute_signature(body) == _sign(body)
