"""Frontend-facing API contracts (pydantic DTOs).

Deliberately separate from internal dataclasses: the HTTP contract exposes
stable concepts only and can never leak SQLite rows, engine internals or
credential material.
"""
