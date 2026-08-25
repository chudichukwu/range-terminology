"""Credential abstraction for exchange adapters.

Secrets live behind the :class:`CredentialStore` port and never enter domain
or exchange models. Implementations:

- :class:`InMemoryCredentialStore`: tests and short-lived processes only.
- :class:`KeychainCredentialStore`: preferred local store (macOS Keychain via
  ``keyring``; other platforms use their native backends transparently).
- :class:`EncryptedFileCredentialStore`: headless fallback storing Fernet-
  encrypted entries, unlocked by a master key from an env var or callback.

Design rules: no plaintext persistence, no hardcoded credentials, no secret
values in logs or exception messages. The future web layer will add per-user
credential namespacing on top of this port.
"""

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast


class KeyringLike(Protocol):
    """Structural subset of the ``keyring`` module API we rely on."""

    def set_password(self, service: str, ref: str, secret: str) -> None: ...
    def get_password(self, service: str, ref: str) -> str | None: ...
    def delete_password(self, service: str, ref: str) -> None: ...


class FernetLike(Protocol):
    """Structural subset of ``cryptography.fernet.Fernet``."""

    def encrypt(self, data: bytes) -> bytes: ...
    def decrypt(self, token: bytes) -> bytes: ...


class CredentialStore(ABC):
    """Port for storing and retrieving named secrets securely."""

    @abstractmethod
    def store(self, ref: str, secret: str) -> None:
        """Persist ``secret`` under ``ref``, encrypted at rest."""

    @abstractmethod
    def retrieve(self, ref: str) -> str:
        """Return the secret stored under ``ref``.

        Raises:
            CredentialLookupError: When ``ref`` has no stored secret.
        """

    @abstractmethod
    def delete(self, ref: str) -> None:
        """Remove the secret stored under ``ref`` if present."""

    @abstractmethod
    def exists(self, ref: str) -> bool:
        """Return True when a secret is stored under ``ref``."""


class CredentialLookupError(KeyError):
    """Raised when a credential reference is not present in a store."""


def redact(secret: object) -> str:
    """Constant mask for any value that might contain secret material."""
    return "[redacted]"


class InMemoryCredentialStore(CredentialStore):
    """Process-local store. Never persists anything; testing convenience."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def store(self, ref: str, secret: str) -> None:
        self._secrets[ref] = secret

    def retrieve(self, ref: str) -> str:
        try:
            return self._secrets[ref]
        except KeyError as exc:
            raise CredentialLookupError(
                f"No credential stored under ref {ref!r}"
            ) from exc

    def delete(self, ref: str) -> None:
        self._secrets.pop(ref, None)

    def exists(self, ref: str) -> bool:
        return ref in self._secrets


class KeychainCredentialStore(CredentialStore):
    """OS keychain-backed store via the ``keyring`` library.

    The keyring module is imported lazily (and injectable for tests) so this
    package stays importable on hosts without it.
    """

    def __init__(
        self,
        service_name: str = "range-trading-terminal",
        keyring_module: KeyringLike | None = None,
    ) -> None:
        self._service = service_name
        if keyring_module is not None:
            self._keyring: KeyringLike = keyring_module
        else:
            import keyring

            self._keyring = cast(KeyringLike, keyring)

    def store(self, ref: str, secret: str) -> None:
        self._keyring.set_password(self._service, ref, secret)

    def retrieve(self, ref: str) -> str:
        value = self._keyring.get_password(self._service, ref)
        if value is None:
            raise CredentialLookupError(f"No credential stored under ref {ref!r}")
        return value

    def delete(self, ref: str) -> None:
        try:
            self._keyring.delete_password(self._service, ref)
        except Exception:  # noqa: BLE001 - venue backends raise varied types
            pass

    def exists(self, ref: str) -> bool:
        return self._keyring.get_password(self._service, ref) is not None


class EncryptedFileCredentialStore(CredentialStore):
    """File-backed store with Fernet encryption at rest.

    Layout: one JSON object mapping refs to Fernet tokens; written atomically
    with owner-only permissions (0600). Master key resolution order: injected
    provider callable, then the ``RANGE_MASTER_KEY`` environment variable. The
    key must be a urlsafe Fernet key string (see ``cryptography.Fernet``).
    """

    def __init__(
        self,
        path: str | Path,
        master_key_provider: Callable[[], str] | None = None,
    ) -> None:
        self._path = Path(path)
        self._master_key_provider = master_key_provider
        self._fernet: FernetLike = self._build_fernet()

    def _resolve_master_key(self) -> str:
        if self._master_key_provider is not None:
            return self._master_key_provider()
        value = os.environ.get("RANGE_MASTER_KEY")
        if not value:
            raise RuntimeError(
                "No master key available: provide master_key_provider or set RANGE_MASTER_KEY"
            )
        return value

    def _build_fernet(self) -> FernetLike:
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(
                "EncryptedFileCredentialStore requires the 'cryptography' package"
            ) from exc
        return Fernet(self._resolve_master_key().encode())

    def _encrypt_secret(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def _decrypt_token(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def _read_entries(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Credential file {self._path} is corrupt: expected an object")
        return {str(k): str(v) for k, v in raw.items()}

    def _write_entries(self, entries: dict[str, str]) -> None:
        import tempfile

        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(entries, separators=(",", ":"))
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".creds-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, self._path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def store(self, ref: str, secret: str) -> None:
        entries = self._read_entries()
        entries[ref] = self._encrypt_secret(secret)
        self._write_entries(entries)

    def retrieve(self, ref: str) -> str:
        entries = self._read_entries()
        if ref not in entries:
            raise CredentialLookupError(f"No credential stored under ref {ref!r}")
        return self._decrypt_token(entries[ref])

    def delete(self, ref: str) -> None:
        entries = self._read_entries()
        entries.pop(ref, None)
        self._write_entries(entries)

    def exists(self, ref: str) -> bool:
        return ref in self._read_entries()


@dataclass(frozen=True)
class CexCredentials:
    """API-key style credentials for CEX venues.

    ``__repr__`` is overridden to prevent accidental leakage through logs,
    tracebacks, or debuggers. Values travel only into adapter configuration.
    """

    api_key: str | None = None
    secret: str | None = None
    password: str | None = None
    uid: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "CexCredentials(api_key=<redacted>, secret=<redacted>)"

    def is_authenticated(self) -> bool:
        """True when at least an API key and secret are present."""
        return bool(self.api_key) and bool(self.secret)

    def as_secret_values(self) -> tuple[str, ...]:
        """All secret-bearing values, used solely for log scrubbing."""
        return tuple(
            value
            for value in (self.api_key, self.secret, self.password, self.uid)
            if value
        )


def load_cex_credentials(store: CredentialStore, ref: str) -> CexCredentials:
    """Rebuild :class:`CexCredentials` from a JSON blob stored under ``ref``."""
    blob = store.retrieve(ref)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Credential blob under {ref!r} is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Credential blob under {ref!r} must be a JSON object")
    allowed = {"api_key", "secret", "password", "uid"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Credential blob has unexpected fields: {sorted(unknown)}")
    return CexCredentials(
        api_key=data.get("api_key"),
        secret=data.get("secret"),
        password=data.get("password"),
        uid=data.get("uid"),
    )


def dump_cex_credentials(credentials: CexCredentials) -> str:
    """Serialize credentials to the canonical JSON blob form for storage."""
    return json.dumps(
        {
            "api_key": credentials.api_key,
            "secret": credentials.secret,
            "password": credentials.password,
            "uid": credentials.uid,
        }
    )
