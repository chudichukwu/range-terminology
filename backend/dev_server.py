"""Local entry point. Public market sources are selected per watchlist item."""
import os
from api.app import create_app

app = create_app(os.environ.get("RANGE_DB_PATH", "range-trading-terminal.db"))
