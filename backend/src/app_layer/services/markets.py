"""Read-only market data facade over the existing Phase 6 service."""

from app_layer.errors import ValidationError
from market_data.models import CandleDataset, Timeframe
from market_data.service import MarketDataService


class MarketDataFacade:
    """Validated application-level access to market data; zero new logic."""

    def __init__(self, market_data: MarketDataService) -> None:
        self._market_data = market_data

    def ticker(self, symbol: str) -> dict[str, object]:
        clean = self._require_symbol(symbol)
        ticker = self._market_data.get_ticker(clean)
        return {
            "symbol": ticker.symbol,
            "bid": ticker.bid,
            "ask": ticker.ask,
            "last": ticker.last,
            "volume": ticker.volume,
            "timestamp_ms": ticker.timestamp,
        }

    def candles(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
        include_current: bool = False,
    ) -> CandleDataset:
        clean = self._require_symbol(symbol)
        parsed = Timeframe.parse(timeframe)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValidationError("limit must be between 1 and 1000")
        return self._market_data.get_recent_candles(
            clean, parsed, limit=limit, include_current=include_current
        )

    def supported_timeframes(self) -> tuple[str, ...]:
        advertised = sorted(
            tf.value for tf in self._market_data.supported_timeframes()
        )
        return tuple(advertised)

    @staticmethod
    def _require_symbol(symbol: str) -> str:
        clean = (symbol or "").strip().upper()
        if "/" not in clean or len(clean) > 20:
            raise ValidationError("symbol must look like BASE/QUOTE (e.g. BTC/USDT)")
        return clean
