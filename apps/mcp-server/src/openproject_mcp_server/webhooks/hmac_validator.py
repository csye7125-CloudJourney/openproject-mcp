"""HMAC-SHA256 validation for inbound OpenProject webhooks.

OpenProject signs the raw request body with a shared secret and puts the
hex digest in the `X-OP-Signature` header. We recompute the digest with
the same secret and compare in constant time. Mismatches raise
InvalidSignature, which the Starlette route turns into a 401.

The secret comes from `WEBHOOK_HMAC_SECRET`. Empty/missing secret makes
the validator fail-closed (every request rejected). We never silently
accept unsigned traffic.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

SIGNATURE_HEADER = "X-OP-Signature"


class InvalidSignature(Exception):
    """Raised when the supplied signature does not match the body HMAC."""


def _load_secret(explicit: Optional[str] = None) -> bytes:
    """Return the HMAC secret bytes, preferring explicit arg over env."""
    if explicit is not None:
        return explicit.encode("utf-8")
    raw = os.environ.get("WEBHOOK_HMAC_SECRET", "")
    return raw.encode("utf-8")


def compute_signature(body: bytes, secret: Optional[str] = None) -> str:
    """Compute the hex-encoded HMAC-SHA256 digest of `body`."""
    key = _load_secret(secret)
    if not key:
        raise InvalidSignature("WEBHOOK_HMAC_SECRET is not configured")
    mac = hmac.new(key, body, hashlib.sha256)
    return mac.hexdigest()


def verify_signature(
    body: bytes,
    supplied: Optional[str],
    secret: Optional[str] = None,
) -> None:
    """Verify `supplied` matches HMAC-SHA256(body, secret). Raises on mismatch.

    Constant-time compare via hmac.compare_digest. Accepts an optional
    `sha256=` prefix on the header since some senders include it.
    """
    if not supplied:
        raise InvalidSignature("missing signature header")
    expected = compute_signature(body, secret)
    candidate = supplied.strip()
    if candidate.lower().startswith("sha256="):
        candidate = candidate[len("sha256="):]
    if not hmac.compare_digest(expected, candidate):
        raise InvalidSignature("signature does not match body")
