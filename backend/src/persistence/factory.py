"""Select local SQLite or managed Postgres without changing service behavior."""
from persistence.adapters.sqlite.database import SqliteDatabase


def is_postgres(location):
    return str(location).startswith(("postgres://", "postgresql://"))


def open_database(location):
    if is_postgres(location):
        from persistence.postgres import PostgresDatabase
        return PostgresDatabase(location)
    return SqliteDatabase(location)
