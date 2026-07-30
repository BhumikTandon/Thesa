"""Temporary card issuer stub.

Stands in for Marqeta until real issuing lands. Returns opaque network tokens
and last4 digits only — never a PAN or CVV. Swap this module for a Marqeta
client behind the same function signatures.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ProvisionedCard:
    """Issuer response after provisioning. No PAN/CVV ever."""

    external_token: str
    last4: str


def provision_card(*, label: str, company_id: uuid.UUID) -> ProvisionedCard:
    """Issue a stub virtual card. Token is opaque and non-reversible to a PAN."""
    # Prefix makes stub tokens easy to spot in logs/DB without revealing secrets.
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(
        f"{company_id}:{label}:{nonce}".encode()
    ).hexdigest()[:32]
    token = f"stub_{digest}"
    last4 = f"{secrets.randbelow(10000):04d}"
    return ProvisionedCard(external_token=token, last4=last4)


def freeze_card(external_token: str) -> None:
    """Stub freeze — real issuer would call Marqeta here. Token validated by caller."""
    if not external_token.startswith("stub_"):
        raise ValueError("unknown issuer token")


def cancel_card(external_token: str) -> None:
    """Stub cancel — real issuer would call Marqeta here."""
    if not external_token.startswith("stub_"):
        raise ValueError("unknown issuer token")
