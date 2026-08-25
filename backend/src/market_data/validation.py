"""Deterministic validation of candle sequences.

Detects duplicate/out-of-order timestamps, missing grid intervals, malformed
records at the normalization boundary, and the presence of still-forming
candles. Problems are never hidden and never "repaired": no candles are
manufactured to fill gaps, none silently dropped. The resulting
:class:`DataQualityReport` lets callers decide whether a dataset is safe for
strategy analysis.
"""

from dataclasses import dataclass

from market_data.models import (
    DataQualityReport,
    MarketCandle,
    QualityIssue,
    Timeframe,
)

_KIND_DUPLICATE = "duplicate_timestamp"
_KIND_OUT_OF_ORDER = "out_of_order_timestamp"
_KIND_MISSING_INTERVAL = "missing_interval"
_KIND_UNCLOSED = "unclosed_candle_present"
_KIND_EMPTY = "empty_series"
_KIND_MEMBER_MISMATCH = "series_member_mismatch"


@dataclass(frozen=True)
class SequenceValidation:
    """Outcome of validating one candle sequence.

    Attributes:
        report: All detected issues.
        sorted_candles: The input candles ordered by open timestamp; ties keep
            first occurrence. Returned separately so callers can work with a
            deterministic ordering without losing sight of original defects.
    """

    report: DataQualityReport
    sorted_candles: tuple[MarketCandle, ...]


def validate_sequence(
    symbol: str,
    timeframe: Timeframe,
    candles: tuple[MarketCandle, ...] | list[MarketCandle],
) -> SequenceValidation:
    """Validate ``candles`` as one symbol/timeframe sequence.

    Checks performed (all deterministic):

    - empty series
    - duplicate open timestamps
    - out-of-order timestamps
    - missing expected intervals on the timeframe grid between consecutive
      candles (explicit ``(gap_start_ms, gap_end_ms)`` ranges)
    - presence of still-forming (unclosed) candles
    """
    duration = timeframe.duration_ms
    issues: list[QualityIssue] = []
    if not candles:
        issues.append(QualityIssue(kind=_KIND_EMPTY, detail="series contains no candles"))
        return SequenceValidation(report=DataQualityReport(issues=tuple(issues)), sorted_candles=())

    seen: set[int] = set()
    duplicates = 0
    out_of_order = 0
    for index, candle in enumerate(candles):
        if candle.symbol != symbol or candle.timeframe is not timeframe:
            issues.append(
                QualityIssue(
                    kind=_KIND_MEMBER_MISMATCH,
                    detail=(
                        f"member {index} is {candle.symbol}/{candle.timeframe.value}, "
                        f"expected {symbol}/{timeframe.value}"
                    ),
                    index=index,
                )
            )
        if candle.timestamp in seen:
            duplicates += 1
            issues.append(
                QualityIssue(
                    kind=_KIND_DUPLICATE,
                    detail=f"duplicate open timestamp {candle.timestamp}",
                    index=index,
                )
            )
        else:
            seen.add(candle.timestamp)
        if index > 0 and candle.timestamp < candles[index - 1].timestamp:
            out_of_order += 1
            issues.append(
                QualityIssue(
                    kind=_KIND_OUT_OF_ORDER,
                    detail=(
                        f"timestamp {candle.timestamp} at index {index} precedes "
                        f"{candles[index - 1].timestamp}"
                    ),
                    index=index,
                )
            )

    ordered = sorted(candles, key=lambda c: c.timestamp)
    unique_sorted = _unique_by_timestamp(tuple(ordered))
    for before, after in zip(unique_sorted, unique_sorted[1:], strict=False):
        delta = after.timestamp - before.timestamp
        if delta <= duration:
            continue
        gap_start = before.close_time_ms
        gap_end = after.timestamp
        missing_count = delta // duration - 1
        issues.append(
            QualityIssue(
                kind=_KIND_MISSING_INTERVAL,
                detail=(
                    f"missing {missing_count} x {timeframe.value} candle(s) "
                    f"between {before.timestamp} and {after.timestamp}"
                ),
                gap_start_ms=gap_start,
                gap_end_ms=gap_end,
            )
        )

    for index, candle in enumerate(candles):
        if not candle.is_closed:
            issues.append(
                QualityIssue(
                    kind=_KIND_UNCLOSED,
                    detail=(
                        f"candle at index {index} (ts {candle.timestamp}) is still forming"
                    ),
                    index=index,
                )
            )

    return SequenceValidation(
        report=DataQualityReport(issues=tuple(issues)), sorted_candles=tuple(ordered)
    )


def mark_unclosed_as_issue(candles: tuple[MarketCandle, ...]) -> tuple[QualityIssue, ...]:
    """Issues for unclosed candles only; used to enrich external reports."""
    return tuple(
        QualityIssue(
            kind=_KIND_UNCLOSED,
            detail=f"candle at index {index} (ts {candle.timestamp}) is still forming",
            index=index,
        )
        for index, candle in enumerate(candles)
        if not candle.is_closed
    )


def _unique_by_timestamp(ordered: tuple[MarketCandle, ...]) -> tuple[MarketCandle, ...]:
    """Keep first occurrence per timestamp on an already-ordered sequence."""
    seen: set[int] = set()
    unique: list[MarketCandle] = []
    for candle in ordered:
        if candle.timestamp not in seen:
            seen.add(candle.timestamp)
            unique.append(candle)
    return tuple(unique)


ISSUE_DUPLICATE_TIMESTAMP = _KIND_DUPLICATE
ISSUE_OUT_OF_ORDER_TIMESTAMP = _KIND_OUT_OF_ORDER
ISSUE_MISSING_INTERVAL = _KIND_MISSING_INTERVAL
ISSUE_UNCLOSED_CANDLE = _KIND_UNCLOSED
ISSUE_EMPTY_SERIES = _KIND_EMPTY
ISSUE_MEMBER_MISMATCH = _KIND_MEMBER_MISMATCH


__all__ = [
    "ISSUE_DUPLICATE_TIMESTAMP",
    "ISSUE_EMPTY_SERIES",
    "ISSUE_MISSING_INTERVAL",
    "ISSUE_MEMBER_MISMATCH",
    "ISSUE_OUT_OF_ORDER_TIMESTAMP",
    "ISSUE_UNCLOSED_CANDLE",
    "SequenceValidation",
    "mark_unclosed_as_issue",
    "validate_sequence",
]
