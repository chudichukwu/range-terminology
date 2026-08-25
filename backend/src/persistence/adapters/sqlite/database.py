"""SQLite implementation of the persistence ports.

SQLite stays behind :mod:`persistence.base`: applications and domain engines
see only repository ABCs and normalized value types. Writes run inside
explicit transactions (a failed batch leaves nothing partially written);
schema creation runs through the ordered migration history in
:mod:`persistence.migrations`.
"""

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.migrations import MIGRATIONS, SCHEMA_VERSION


def utc_clock_ms() -> int:
    return time.time_ns() // 1_000_000


class SqliteDatabase:
    """Thin, explicit SQLite connection owner with transaction + migration support."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._path = Path(path)
        self._clock_ms = clock_ms if clock_ms is not None else utc_clock_ms
        if self._path != Path(":memory:"):
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._path),
            isolation_level="DEFERRED",
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    # ----- schema -----

    def schema_version(self) -> int:
        """Current applied schema version; 0 for an uninitialized database."""
        table = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if table is None:
            return 0
        row = self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def ensure_schema(self) -> int:
        """Apply pending migrations; returns the resulting schema version.

        Each migration runs inside its own transaction together with its
        bookkeeping row, so a crash can never leave a half-applied step.
        """
        current = self.schema_version()
        if current > SCHEMA_VERSION:
            raise PersistenceError(
                PersistenceErrorCode.SCHEMA_ERROR,
                f"database schema version {current} is newer than supported {SCHEMA_VERSION}",
                metadata={"db_version": current, "supported": SCHEMA_VERSION},
            )
        for migration in MIGRATIONS:
            if migration.version <= current:
                continue
            with self.transaction() as conn:
                for statement in migration.statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at_ms) VALUES (?, ?)",
                    (migration.version, self._clock_ms()),
                )
        return self.schema_version()

    # ----- transactions -----

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit transaction scope: commit on success, rollback on error."""
        try:
            yield self._conn
            self._conn.commit()
        except sqlite3.Error as exc:
            self._conn.rollback()
            raise self._wrap(exc) from exc
        except BaseException:
            self._conn.rollback()
            raise

    @staticmethod
    def _wrap(exc: sqlite3.Error) -> PersistenceError:
        code = (
            PersistenceErrorCode.INTEGRITY_ERROR
            if isinstance(exc, sqlite3.IntegrityError)
            else PersistenceErrorCode.TRANSACTION_FAILED
        )
        return PersistenceError(
            code,
            f"sqlite failure: {type(exc).__name__}: {exc}",
            metadata={"sqlite_error_type": type(exc).__name__},
        )
