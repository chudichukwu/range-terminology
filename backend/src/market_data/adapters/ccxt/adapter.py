"""ExchangePort-backed :class:`~market_data.base.MarketDataPort`.

Composes the Phase 4 exchange layer instead of duplicating it: all payload
normalization, CCXT isolation, and error translation already live there. This
adapter adds market-data semantics on top: canonical timeframes, advertised
capability reporting, and windowed historical fetching via ``since_ms``.
"""

from exchange.base import ExchangePort
from exchange.models import Candle, Ticker
from market_data.base import MarketDataPort
from market_data.errors import MarketDataError, MarketDataErrorCode
from market_data.models import Timeframe


class ExchangeMarketDataProvider(MarketDataPort):
    """Serves market data from any Phase 4 :class:`ExchangePort` instance."""

    def __init__(
        self,
        exchange: ExchangePort,
        *,
        supported_timeframes: frozenset[Timeframe] | tuple[Timeframe, ...] | None = None,
    ) -> None:
        """Compose with an exchange port.

        Args:
            exchange: The Phase 4 port (e.g. a ``CcxtAdapter``).
            supported_timeframes: Explicit override; when omitted, derived
                from the venue's own advertisement when it exposes one and
                left EMPTY otherwise — never invented.
        """
        self._exchange = exchange
        if supported_timeframes is not None:
            self._timeframes = frozenset(supported_timeframes)
        else:
            self._timeframes = self._derive_timeframes()

    def _derive_timeframes(self) -> frozenset[Timeframe]:
        advertised = getattr(self._exchange, "supported_timeframes", ())
        result: set[Timeframe] = set()
        for raw in advertised or ():
            try:
                result.add(Timeframe.parse(raw))
            except ValueError:
                continue  # venue advertises something outside our canon; ignore honestly
        return frozenset(result)

    @property
    def venue_id(self) -> str:
        return self._exchange.venue_id

    def get_ticker(self, symbol: str) -> Ticker:
        return self._exchange.get_ticker(symbol)

    def fetch_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        limit: int = 200,
        since_ms: int | None = None,
    ) -> tuple[Candle, ...]:
        return self._exchange.get_ohlcv(symbol, timeframe.value, limit, since_ms=since_ms)

    def supported_timeframes(self) -> frozenset[Timeframe]:
        return self._timeframes

    def require_timeframe(self, timeframe: Timeframe) -> None:
        """Raise when this provider explicitly does not serve ``timeframe``.

        An empty advertised set means "unknown" and passes through so the
        provider's own runtime answer decides.
        """
        advertised = self._timeframes
        if advertised and timeframe not in advertised:
            raise MarketDataError(
                MarketDataErrorCode.TIMEFRAME_UNSUPPORTED,
                f"{self.venue_id} does not advertise timeframe {timeframe.value!r}",
                metadata={
                    "timeframe": timeframe.value,
                    "supported": sorted(tf.value for tf in advertised),
                },
            )


__all__ = ["ExchangeMarketDataProvider"]
