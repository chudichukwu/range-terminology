"""Explicit schema versioning and migrations.

The database carries a known integer schema version recorded in
``schema_migrations``. Each migration is a named, ordered set of SQL
statements applied inside its own transaction; partially applied migrations
are impossible. No external migration framework — deliberate and small.
"""

from dataclasses import dataclass

SCHEMA_VERSION = 3

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

_V2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id          TEXT PRIMARY KEY,
        config_hash     TEXT NOT NULL,
        symbol          TEXT NOT NULL,
        timeframe       TEXT NOT NULL,
        period_start_ms INTEGER NOT NULL,
        period_end_ms   INTEGER NOT NULL,
        initial_capital REAL NOT NULL,
        final_equity    REAL NOT NULL,
        peak_equity     REAL NOT NULL,
        max_drawdown    REAL NOT NULL,
        total_trades    INTEGER NOT NULL,
        stats_json      TEXT NOT NULL,
        config_json     TEXT NOT NULL,
        engine_version  TEXT NOT NULL,
        created_at_ms   INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_symbol ON backtest_runs (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_config ON backtest_runs (config_hash)",
)

_V3_STATEMENTS: tuple[str, ...] = (
    # Phase 8 compatibility: runs gain an optional owner for user isolation.
    "ALTER TABLE backtest_runs ADD COLUMN owner_user_id TEXT",
    """
    CREATE TABLE IF NOT EXISTS users (
        id              TEXT PRIMARY KEY,
        email           TEXT NOT NULL UNIQUE,
        password_hash   TEXT NOT NULL,
        role            TEXT NOT NULL CHECK (role IN ('user', 'owner')),
        active          INTEGER NOT NULL CHECK (active IN (0, 1)),
        created_at_ms   INTEGER NOT NULL,
        updated_at_ms   INTEGER NOT NULL,
        last_login_at_ms INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id           TEXT PRIMARY KEY,
        user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_digest TEXT NOT NULL UNIQUE,
        created_at_ms INTEGER NOT NULL,
        expires_at_ms INTEGER NOT NULL,
        revoked_at_ms INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id)",
    """
    CREATE TABLE IF NOT EXISTS watchlists (
        id            TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name          TEXT NOT NULL,
        created_at_ms INTEGER NOT NULL,
        updated_at_ms INTEGER NOT NULL,
        UNIQUE (owner_user_id, name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watchlists_owner ON watchlists (owner_user_id)",
    """
    CREATE TABLE IF NOT EXISTS watchlist_items (
        id            TEXT PRIMARY KEY,
        watchlist_id  TEXT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
        symbol        TEXT NOT NULL,
        venue_id      TEXT NOT NULL,
        enabled       INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        notes         TEXT NOT NULL DEFAULT '',
        sort_order    INTEGER NOT NULL DEFAULT 0,
        created_at_ms INTEGER NOT NULL
    )
    """,
    (
        "CREATE INDEX IF NOT EXISTS idx_watchlist_items_list "
        "ON watchlist_items (watchlist_id, sort_order)"
    ),
    """
    CREATE TABLE IF NOT EXISTS strategy_configs (
        id            TEXT PRIMARY KEY,
        owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name          TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        active        INTEGER NOT NULL CHECK (active IN (0, 1)),
        created_at_ms INTEGER NOT NULL,
        updated_at_ms INTEGER NOT NULL,
        UNIQUE (owner_user_id, name)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_strategies_owner ON strategy_configs (owner_user_id)",
    """
    CREATE TABLE IF NOT EXISTS exchange_connections (
        id             TEXT PRIMARY KEY,
        owner_user_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        venue_id       TEXT NOT NULL,
        display_name   TEXT NOT NULL,
        status         TEXT NOT NULL,
        credential_ref TEXT NOT NULL,
        sandbox        INTEGER NOT NULL CHECK (sandbox IN (0, 1)),
        created_at_ms  INTEGER NOT NULL,
        updated_at_ms  INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_connections_owner ON exchange_connections (owner_user_id)",
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id            TEXT PRIMARY KEY,
        actor_user_id TEXT,
        action        TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT,
        timestamp_ms  INTEGER NOT NULL,
        outcome       TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log (timestamp_ms)",
    "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log (actor_user_id)",
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
    Migration(version=2, name="backtest_runs", statements=_V2_STATEMENTS),
    Migration(version=3, name="application_layer", statements=_V3_STATEMENTS),
)

assert MIGRATIONS[-1].version == SCHEMA_VERSION, "migration history must end at SCHEMA_VERSION"
assert [m.version for m in MIGRATIONS] == list(range(1, SCHEMA_VERSION + 1)), (
    "migration versions must be contiguous starting at 1"
)
