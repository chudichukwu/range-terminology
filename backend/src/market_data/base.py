"""MarketDataPort: the provider-facing boundary for market data.

Sits ABOVE the Phase 4 :class:`exchange.base.ExchangePort` (whose CCXT
adapter already normalizes ticker/OHLCV payloads) and is deliberately
implementable by non-CCXT providers later (TradingView, DEX indexers, files)
without touching any engine. Consumers see only
:mod:`market_data.models` types plus :class:`~market_data.errors.MarketDataError`.
"""

from abc import ABC, abstractmethod

from exchange.models import Candle, Ticker
from market_data.models import Timeframe


class MarketDataPort(ABC):
    """Normalized market data operations every provider implements."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> Ticker:
        """Latest quote snapshot for ``symbol``."""

    @abstractmethod
    def fetch_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        limit: int = 200,
        since_ms: int | None = None,
    ) -> tuple[Candle, ...]:
        """Candles opening at/after ``since_ms`` (or the most recent ones).

        Rows are project-normalized :class:`exchange.models.Candle` values —
        the same shape Phase 4 adapters already produce, so CCXT stays an
        implementation detail. Providers return whatever they honestly have;
        callers assess quality separately.
        """

    @abstractmethod
    def supported_timeframes(self) -> frozenset[Timeframe]:
        """Timeframes this provider advertises; empty means unadvertised."""
