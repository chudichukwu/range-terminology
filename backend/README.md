# Range Trading Terminal — Backend (Phase 1)

Domain layer of a web-based crypto range-trading terminal. This package contains
only the pluggable range-detection engine and its supporting primitives: pure
functions over pandas/numpy, zero I/O, fully unit-testable.

## Setup

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Checks

```bash
.venv/bin/pytest -v
.venv/bin/ruff check .
.venv/bin/mypy
```

## Usage

```python
from range_engine import RangeEngineFactory

state = RangeEngineFactory.detect(df, {
    "mode": "structural",          # default when omitted; also: manual,
    "params": {"lookback": 100},   # volatility, oscillator_confirmed
})
state.status        # VALID | DEGENERATE | INSUFFICIENT_DATA
state.range_high
state.confidence    # heuristic score in [0, 1], not a probability
```

Deferred layers (API, auth, exchange adapters, frontend) are intentionally absent.
