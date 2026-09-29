"""Dataset coverage — authoritative historical dataset metadata.

Exposes `DatasetSummary` facts already persisted via `CandleRepository`.
No frontend calculations, no inferred coverage.
"""

from fastapi import APIRouter

from api.dependencies import ContainerDep, CurrentUser

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _out(summary) -> dict[str, object]:  # type: ignore[no-untyped-def]
    issues = []
    for issue in getattr(summary, "issues", ()):
        # Sanitized, typed projection of the already-persisted quality diagnostic
        issues.append(
            {
                "kind": getattr(issue, "kind", ""),
                "detail": getattr(issue, "detail", ""),
                "index": getattr(issue, "index", None),
                "gap_start_ms": getattr(issue, "gap_start_ms", None),
                "gap_end_ms": getattr(issue, "gap_end_ms", None),
            }
        )
    return {
        "symbol": summary.symbol,
        "timeframe": summary.timeframe,
        "source": summary.source,
        "candle_count": summary.candle_count,
        "first_timestamp_ms": summary.first_timestamp_ms,
        "last_timestamp_ms": summary.last_timestamp_ms,
        "quality_status": summary.quality_status.value,
        "issues": issues,
        "ingested_at_ms": summary.ingested_at_ms,
        "updated_at_ms": summary.updated_at_ms,
    }


@router.get("", response_model=None)
def list_datasets(
    container: ContainerDep, user: CurrentUser
) -> list[dict[str, object]]:
    # Authenticated readable — datasets are historical research facts,
    # not owner-scoped secrets. OwnerRequired is not used here.
    _ = user
    summaries = container.store.list_dataset_summaries()
    return [_out(s) for s in summaries]
