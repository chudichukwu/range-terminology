"""Fail-closed entry point for the single-instance private cloud deployment."""

import os
import sqlite3
from pathlib import Path

from api.app import create_app


def create_production_app():
    raw_path = os.environ.get("RANGE_DB_PATH", "")
    path = Path(raw_path)
    if not raw_path or not path.is_absolute() or not path.is_file():
        raise RuntimeError("RANGE_DB_PATH must name a restored database on a persistent volume")
    # Read-only preflight: a typo must never create an empty public database.
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        try:
            owner = connection.execute(
                "SELECT 1 FROM users WHERE role='owner' AND active=1 LIMIT 1"
            ).fetchone()
        except sqlite3.Error as exc:
            raise RuntimeError("Restore the existing Grandblue database before startup") from exc
    if owner is None:
        raise RuntimeError("The restored database must contain an active owner")
    os.environ.setdefault("GRANDBLUE_PRIVATE_BETA", "1")
    os.environ.setdefault("GRANDBLUE_ALLOWED_ORIGINS", "")
    return create_app(str(path))
