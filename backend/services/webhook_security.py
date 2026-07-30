"""HMAC signature + timestamp checks for the JIT webhook.

Signature verification runs on the raw body *before* JSON parsing. Uses
constant-time comparison. Replay window is enforced via timestamp skew plus
the webhook_events idempotency table (callers must check event_id separately).
"""

from __future__ import annotations

import hashlib
import hmac
import time


def build_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Canonical signature: HMAC-SHA256(secret, "{timestamp}.{body}")."""
    message = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(
        secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def verify_signature(
    *,
    secret: str,
    timestamp: str,
    body: bytes,
    provided: str,
    skew_seconds: int,
    now: float | None = None,
) -> str | None:
    """Return an error reason if verification fails, else None.

    Checks (in order): timestamp parseable, within skew window, signature
    matches with hmac.compare_digest. Never raises.
    """
    now = time.time() if now is None else now
    try:
        ts = float(timestamp)
    except (TypeError, ValueError):
        return "invalid_timestamp"

    if abs(now - ts) > skew_seconds:
        return "timestamp_out_of_window"

    expected = build_signature(secret, timestamp, body)
    if not hmac.compare_digest(expected, provided.strip()):
        return "bad_signature"
    return None
