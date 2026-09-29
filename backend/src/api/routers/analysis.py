"""Pair analysis — backend-provided market + range + regime + signal + risk.

Uses the existing engines; this router only exposes their results to the
frontend. No domain logic is reimplemented here.
"""

from fastapi import APIRouter, Query

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.analysis import AnalysisOut
from app_layer.services.analysis import PairAnalysisService
from app_layer.services.providers import public_source

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/pair", response_model=AnalysisOut)
def pair_analysis(
    container: ContainerDep,
    user: CurrentUser,
    symbol: str = Query(..., description="BASE/QUOTE e.g. BTC/USDT"),
    timeframe: str = Query(default="1h"),
    strategy_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    venue: str | None = Query(default=None),
) -> dict[str, object]:
    if venue:
        source = public_source(venue)
        with source.lock:
            result = PairAnalysisService(source.facade, container.strategies).analyze(
                user, symbol, timeframe, strategy_id=strategy_id, limit=limit)
        return {**result, "venue": venue}
    svc = PairAnalysisService(container.markets, container.strategies)
    return svc.analyze(user, symbol, timeframe, strategy_id=strategy_id, limit=limit)


@router.get("/pair/{symbol_dashed}", response_model=AnalysisOut)
def pair_analysis_dashed(
    symbol_dashed: str,
    container: ContainerDep,
    user: CurrentUser,
    timeframe: str = Query(default="1h"),
    strategy_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    venue: str | None = Query(default=None),
) -> dict[str, object]:
    return pair_analysis(container, user, symbol_dashed.replace("-", "/"), timeframe,
                         strategy_id, limit, venue)
