"""Explicit schema versioning and migrations.

The database carries a known integer schema version recorded in
``schema_migrations``. Each migration is a named, ordered set of SQL
statements applied inside its own transaction; partially applied migrations
are impossible. No external migration framework — deliberate and small.
"""

from dataclasses import dataclass

SCHEMA_VERSION = 1

_V1_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version       INTEGER PRIMARY KEY,
        applied_at_ms INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candles (
        symbol       TEXT    NOT NULL,
        timeframe    TEXT    NOT NULL,
        ts           INTEGER NOT NULL,
        open         REAL    NOT NULL,
        high         REAL    NOT NULL,
        low          REAL    NOT NULL,
        close        REAL    NOT NULL,
        volume       REAL,
        is_closed    INTEGER NOT NULL CHECK (is_closed IN (0, 1)),
        source       TEXT    NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        PRIMARY KEY (symbol, timeframe, ts, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS datasets (
        symbol         TEXT NOT NULL,
        timeframe      TEXT NOT NULL,
        source         TEXT NOT NULL,
        first_ts       INTEGER,
        last_ts        INTEGER,
        candle_count   INTEGER NOT NULL,
        quality_status TEXT NOT NULL CHECK (quality_status IN ('clean', 'warnings')),
        issues_json    TEXT NOT NULL,
        ingested_at_ms INTEGER NOT NULL,
        updated_at_ms  INTEGER NOT NULL,
        PRIMARY KEY (symbol, timeframe, source)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        trade_id      TEXT PRIMARY KEY,
        execution_ref TEXT,
        symbol        TEXT NOT NULL,
        timeframe     TEXT,
        direction     TEXT NOT NULL CHECK (direction IN ('long', 'short')),
        quantity      REAL NOT NULL,
        entry_price   REAL NOT NULL,
        exit_price    REAL,
        opened_at_ms  INTEGER NOT NULL,
        closed_at_ms  INTEGER,
        status        TEXT NOT NULL CHECK (status IN ('open', 'closed')),
        realized_pnl  REAL,
        fees          REAL,
        slippage      REAL,
        risk_amount   REAL,
        realized_r    REAL,
        result        TEXT CHECK (result IN ('win', 'loss', 'breakeven') OR result IS NULL),
        strategy_id   TEXT,
        config_hash   TEXT,
        context_json  TEXT,
        created_at_ms INTEGER NOT NULL,
        updated_at_ms INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades (closed_at_ms)",
    "CREATE INDEX IF NOT EXISTS idx_trades_result ON trades (result)",
    "CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades (strategy_id)",
)


@dataclass(frozen=True)
class Migration:
    """One explicit schema migration step."""

    version: int
    name: str
    statements: tuple[str, ...]


#: Ordered migration history; index i upgrades schema to ``version = i + 1``.
MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="initial_schema", statements=_V1_STATEMENTS),
)

assert MIGRATIONS[-1].version == SCHEMA_VERSION, "migration history must end at SCHEMA_VERSION"
assert [m.version for m in MIGRATIONS] == list(range(1, SCHEMA_VERSION + 1)), (
    "migration versions must be contiguous starting at 1"
)
