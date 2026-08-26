"""app_layer: application services orchestrating engines and persistence.

This layer contains use-case orchestration ONLY. Domain logic lives in the
engines; storage lives behind ports implemented by persistence adapters; the
HTTP layer (``api``) maps these services onto FastAPI.
"""

from app_layer.errors import (
    AppError,
    AppErrorCode,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
    ValidationError,
)
from app_layer.services import (
    AuditService,
    BacktestService,
    ExchangeConnectionService,
    MarketDataFacade,
    StrategyConfigService,
    UserService,
    WatchlistService,
)

__version__ = "0.1.0"

__all__ = [
    "AppError",
    "AppErrorCode",
    "AuditService",
    "BacktestService",
    "ConflictError",
    "ExchangeConnectionService",
    "ForbiddenError",
    "MarketDataFacade",
    "NotFoundError",
    "StrategyConfigService",
    "UnauthenticatedError",
    "UserService",
    "ValidationError",
    "WatchlistService",
    "__version__",
]
