"""Storage adapters implementing the persistence ports.

SQLite today; the port boundary in :mod:`persistence.base` keeps future
backends (PostgreSQL, etc.) drop-in without touching callers.
"""
