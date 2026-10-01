"""Postgres connection adapter for the shared, parameterized repository SQL.

Application tables live in a private schema, never Supabase's exposed public
schema. Local SQLite remains available for development and rollback.
"""
import re
from contextlib import contextmanager
from threading import RLock

import psycopg

from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.migrations import MIGRATIONS, SCHEMA_VERSION
from persistence.adapters.sqlite.database import utc_clock_ms


class Record(dict):
    def __init__(self, names, values):
        super().__init__(zip(names, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    names = [col.name for col in cursor.description] if cursor.description else []
    return lambda values: Record(names, values)


def postgres_sql(statement):
    # Only internal repository SQL passes through this adapter. Preserve quoted
    # string literals; all user data is still supplied separately as parameters.
    parts = re.split(r"('(?:''|[^'])*')", statement)
    for index in range(0, len(parts), 2):
        parts[index] = parts[index].replace("?", "%s")
        parts[index] = re.sub(r"\bINTEGER\b", "BIGINT", parts[index], flags=re.I)
        parts[index] = re.sub(r"\bREAL\b", "DOUBLE PRECISION", parts[index], flags=re.I)
    return "".join(parts)


class Connection:
    def __init__(self, url):
        self.raw = psycopg.connect(url, autocommit=True, row_factory=record_factory,
                                   prepare_threshold=None, connect_timeout=15)
        self.raw.execute("SET search_path TO grandblue")

    def execute(self, statement, parameters=()):
        return self.raw.execute(postgres_sql(statement), parameters or None)

    def executescript(self, script):
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def __enter__(self):
        self._transaction = self.raw.transaction()
        self._transaction.__enter__()
        return self

    def __exit__(self, *args):
        return self._transaction.__exit__(*args)

    def close(self):
        self.raw.close()


class PostgresDatabase:
    def __init__(self, url):
        self._lock = RLock()
        self._conn = Connection(url)

    def close(self):
        self._conn.close()

    @contextmanager
    def transaction(self):
        with self._lock:
            try:
                with self._conn.raw.transaction():
                    yield self._conn
            except psycopg.Error as exc:
                code = (PersistenceErrorCode.INTEGRITY_ERROR
                        if isinstance(exc, psycopg.IntegrityError)
                        else PersistenceErrorCode.TRANSACTION_FAILED)
                # Do not expose query parameters or connection details in errors.
                raise PersistenceError(code, "Database transaction failed") from exc

    def schema_version(self):
        with self.transaction() as connection:
            if connection.execute("SELECT to_regclass('grandblue.schema_migrations')").fetchone()[0] is None:
                return 0
            return connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]

    def ensure_schema(self):
        # Serialize migrations even if an old/new service overlaps on deploy.
        with self.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(71943215)")
            connection.execute("CREATE SCHEMA IF NOT EXISTS grandblue")
            connection.execute("REVOKE ALL ON SCHEMA grandblue FROM PUBLIC")
            current = self.schema_version()
            if current > SCHEMA_VERSION:
                raise RuntimeError("Database schema is newer than this application")
            for migration in MIGRATIONS:
                if migration.version <= current:
                    continue
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute("INSERT INTO schema_migrations VALUES (?, ?)",
                                   (migration.version, utc_clock_ms()))
        return self.schema_version()
