"""Security primitives: password hashing and opaque session tokens.

CHOSEN APPROACH (documented deliberately):

Passwords — ``hashlib.scrypt`` from the Python standard library. Scrypt is a
modern memory-hard KDF in the same family as Argon2id; using the stdlib
implementation avoids new native dependencies while remaining a recognized,
secure choice (OWASP-approved when configured with sufficient cost).
Stored format: ``scrypt$<n>$<r>$<p>$<salt_hex>$<dk_hex>``. Verification is
constant-time via ``hmac.compare_digest``. Plaintext passwords never persist
and never appear in logs or errors.

Sessions — server-side opaque bearer tokens. The token itself is shown once
at login; only its SHA-256 digest is persisted, so a database leak does not
yield usable credentials. Sessions expire, are revocable individually or
per-user (admin action), and require an ACTIVE user on every request. This
suits a browser-based multi-user app better than stateless JWTs here because
revocation must be immediate for the admin capabilities required by Phase 9.

No custom cryptography is invented anywhere in this module.
"""

import hashlib
import hmac
import secrets

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 64


def hash_password(password: str) -> str:
    """Hash ``password`` with scrypt; returns the self-describing stash."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("password must be a string of at least 8 characters")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return (
        f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}"
        f"${salt.hex()}${derived.hex()}"
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time password verification against a stored scrypt hash."""
    try:
        scheme, n_raw, r_raw, p_raw, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(dk_hex)
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


def generate_session_token() -> str:
    """A fresh opaque bearer token (256 bits of CSPRNG entropy)."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """SHA-256 hex digest used as the persistent session identifier."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


SENSITIVE_KEY_MARKERS = ("secret", "password", "token", "api_key", "apikey", "credential")


def scrub_sensitive(payload: dict[str, object]) -> dict[str, object]:
    """Defense-in-depth redaction for metadata headed to logs/audit."""
    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(marker in lowered for marker in SENSITIVE_KEY_MARKERS):
            cleaned[key] = "[redacted]"
        else:
            cleaned[key] = value
    return cleaned


__all__ = [
    "generate_session_token",
    "hash_password",
    "scrub_sensitive",
    "token_digest",
    "verify_password",
]
