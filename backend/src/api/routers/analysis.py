"""Pair analysis — backend-provided market + range + regime + signal + risk.

Uses the existing engines; this router only exposes their results to the
frontend. No domain logic is reimplemented here.
"""

from fastapi import APIRouter, Query

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.analysis import AnalysisOut
from app_layer.services.analysis import PairAnalysisService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/pair", response_model=AnalysisOut)
def pair_analysis(
    container: ContainerDep,
    user: CurrentUser,
    symbol: str = Query(..., description="BASE/QUOTE e.g. BTC/USDT"),
    timeframe: str = Query(default="1h"),
    strategy_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    svc = PairAnalysisService(container.markets, container.strategies)
    return svc.analyze(user, symbol, timeframe, strategy_id=strategy_id, limit=limit)


@router.get("/pair/{symbol_dashed}", response_model=AnalysisOut)
def pair_analysis_dashed(
    symbol_dashed: str,
    container: ContainerDep,
    user: CurrentUser,
    timeframe: str = Query(default="1h"),
    strategy_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    svc = PairAnalysisService(container.markets, container.strategies)
    return svc.analyze(
        user, symbol_dashed.replace("-", "/"), timeframe, strategy_id=strategy_id, limit=limit
    )
