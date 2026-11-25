"""Cryptographic capability token utilities and security helpers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid


def generate_capability_token() -> str:
    """Generate a 256-bit cryptographically secure URL-safe capability token."""
    return secrets.token_urlsafe(32)


def hash_capability_token(token: str) -> str:
    """Compute the SHA-256 digest of a capability token."""
    if not token or not isinstance(token, str):
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_capability_token(stored_hash: str, supplied_token: str) -> bool:
    """Verify a client-supplied token against stored hash in constant time."""
    if not stored_hash or not supplied_token:
        return False
    computed_hash = hash_capability_token(supplied_token)
    return hmac.compare_digest(stored_hash, computed_hash)


def generate_internal_session_id() -> str:
    """Generate an internal UUID4 identifier for directory isolation."""
    return str(uuid.uuid4())
