"""One-shot SQLite -> empty private Postgres schema migration.

Run with writes stopped, DATABASE_URL set privately, and --source pointing to a
SQLite backup. Never overwrites cloud data. Existing sessions are not migrated.
"""
import argparse
import os
import sqlite3
from pathlib import Path

from app_layer.services.alerts import AlertService
from persistence.postgres import PostgresDatabase
from persistence.migrations import SCHEMA_VERSION

TABLES = (
    "users", "candles", "datasets", "trades", "backtest_runs", "watchlists",
    "watchlist_items", "strategy_configs", "exchange_connections", "audit_log",
    "journal_entries", "observed_ranges", "alert_rules", "alert_events", "alert_states",
)


def migrate(source_path, url):
    # A consistent snapshot even when WAL is present; never modify the source.
    snapshot = sqlite3.connect(":memory:")
    source = sqlite3.connect(Path(source_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        source.backup(snapshot)
    finally:
        source.close()
    version = snapshot.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
    if version != SCHEMA_VERSION:
        snapshot.close()
        raise RuntimeError("Upgrade the local database before migration")
    target = PostgresDatabase(url)
    try:
        target.ensure_schema()
        alerts = AlertService(url)
        alerts.close()
        counts = {}
        with target.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(71943216)")
            connection.execute("LOCK TABLE " + ",".join(TABLES) + ",sessions IN ACCESS EXCLUSIVE MODE")
            for table in (*TABLES, "sessions"):
                if connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]:
                    raise RuntimeError("Migration requires an empty destination; no data overwritten")
            for table in TABLES:
                exists = snapshot.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    counts[table] = 0
                    continue
                cursor = snapshot.execute(f'SELECT * FROM "{table}"')
                columns = [description[0] for description in cursor.description]
                names = ",".join('"' + name + '"' for name in columns)
                placeholders = ",".join("?" for _ in columns)
                rows = cursor.fetchall()
                for row in rows:
                    connection.execute(f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})', row)
                restored = connection.execute(f'SELECT {names} FROM "{table}"').fetchall()
                if sorted(map(repr, rows)) != sorted(repr(tuple(row.values())) for row in restored):
                    raise RuntimeError(f"Verification failed for {table}; migration rolled back")
                counts[table] = len(rows)
            if not connection.execute("SELECT 1 FROM users WHERE role='owner' AND active=1").fetchone():
                raise RuntimeError("Source must contain an active owner")
        return counts
    finally:
        snapshot.close()
        target.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    counts = migrate(args.source, os.environ["DATABASE_URL"])
    print("Verified migrated row counts:", counts)
    print("Sessions were excluded. Sign in again after deployment.")
