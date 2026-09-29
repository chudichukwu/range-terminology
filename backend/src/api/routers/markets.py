"""Market-data endpoints delegating to the Phase 6 service via the facade."""

from fastapi import APIRouter, Query

from api.dependencies import ContainerDep, CurrentUser
from app_layer.services.providers import SOURCES, public_source

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("/sources")
def sources(_user: CurrentUser) -> list[dict[str, str]]:
    return [{"id": key, "name": name} for key, name in SOURCES.items()]


@router.get("/symbols")
def symbols(_user: CurrentUser, venue: str, q: str = "") -> list[str]:
    source = public_source(venue)
    with source.lock:
        return [s for s in source.adapter.get_markets() if q.upper() in s.upper()][:200]


@router.get("/timeframes")
def supported_timeframes(container: ContainerDep, _user: CurrentUser, venue: str | None = None) -> dict[str, object]:
    facade = public_source(venue).facade if venue else container.markets
    return {"timeframes": list(facade.supported_timeframes())}


@router.get("/{symbol_dashed}/ticker")
def ticker(symbol_dashed: str, container: ContainerDep, _user: CurrentUser) -> dict[str, object]:
    """Path symbols use dash form (``BTC-USDT``) so URLs stay unescaped."""
    return container.markets.ticker(symbol_dashed.replace("-", "/"))


@router.get("/{symbol_dashed}/candles")
def candles(
    symbol_dashed: str,
    container: ContainerDep,
    _user: CurrentUser,
    timeframe: str = Query(default="1h"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, object]:
    dataset = container.markets.candles(
        symbol_dashed.replace("-", "/"), timeframe, limit=limit,
        include_current=False,
    )
    return {
        "symbol": dataset.symbol,
        "timeframe": dataset.timeframe.value,
        "quality_issues": sorted(dataset.quality.issue_kinds),
        "candles": [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "is_closed": candle.is_closed,
            }
            for candle in dataset.candles
        ],
    }
