"""Unit tests for the range_engine domain package.

All fixtures are deterministic synthetic OHLCV frames — no network, no files.
"""

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd
import pytest

from range_engine import (
    ManualRangeDetector,
    OscillatorConfirmedRangeDetector,
    RangeDetector,
    RangeEngineFactory,
    RangeState,
    RangeStatus,
    StructuralRangeDetector,
    VolatilityRangeDetector,
)

WIGGLE = 0.25


def make_candles(
    closes: list[float] | np.ndarray,
    *,
    volume: float = 1000.0,
    wiggle: float = WIGGLE,
) -> pd.DataFrame:
    """Build a deterministic OHLCV frame from a close-price series.

    Opens are the previous closes; highs/lows sit a fixed wiggle above/below
    the bar body so pivot and band math stay fully predictable. A wiggle of
    ``0.0`` produces true zero-volatility bars (open == high == low == close).
    """
    close_arr = np.asarray(closes, dtype=float)
    open_arr = np.concatenate(([close_arr[0]], close_arr[:-1]))
    high_arr = np.maximum(open_arr, close_arr) + wiggle
    low_arr = np.minimum(open_arr, close_arr) - wiggle
    timestamps = pd.date_range("2024-01-01", periods=len(close_arr), freq="1h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_arr,
            "high": high_arr,
            "low": low_arr,
            "close": close_arr,
            "volume": float(volume),
        }
    )


def ranging_closes(bars: int = 120, base: float = 105.0, amplitude: float = 5.0) -> np.ndarray:
    """Deterministic sine wave oscillating between 100 and 110."""
    return base + amplitude * np.sin(np.arange(bars) * np.pi / 10.0)


def uptrend_closes(bars: int = 150) -> np.ndarray:
    """Deterministic steady uptrend with a small zigzag."""
    return 100.0 + 0.6 * np.arange(bars) + 1.5 * np.sin(np.arange(bars) * np.pi / 6.0)


def flat_closes(bars: int = 60, price: float = 105.0) -> np.ndarray:
    """Perfectly flat zero-volatility series."""
    return np.full(bars, price)


def decline_into_floor_closes() -> np.ndarray:
    """Hard decline from 200 to 100 then six flat bars at the floor."""
    decline = np.linspace(200.0, 100.0, 30)
    return np.concatenate((decline, np.full(6, 100.0)))


def rally_into_ceiling_closes() -> np.ndarray:
    """Hard rally from 50 to 100 then six flat bars at the ceiling."""
    rally = np.linspace(50.0, 100.0, 30)
    return np.concatenate((rally, np.full(6, 100.0)))


def mid_range_closes(bars: int = 40) -> np.ndarray:
    """Prices hovering around the middle of the [100, 110] range."""
    return 105.0 + np.where(np.arange(bars) % 2 == 0, -1.0, 1.0)


class StubDetector(RangeDetector):
    """Test double returning a canned state and recording calls."""

    def __init__(self, state: RangeState) -> None:
        self.state = state
        self.last_config: Mapping[str, object] | None = None

    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        self.last_config = config
        return self.state


class TestRangeState:
    def test_rejects_low_above_high(self) -> None:
        with pytest.raises(ValueError, match="range_low"):
            RangeState(100.0, 110.0, "manual", 0.9, {}, RangeStatus.VALID)

    def test_accepts_zero_width(self) -> None:
        state = RangeState(100.0, 100.0, "manual", 0.0, {}, RangeStatus.DEGENERATE)
        assert state.range_width == 0.0

    def test_rejects_confidence_out_of_bounds(self) -> None:
        for bad in (-0.1, 1.5):
            with pytest.raises(ValueError, match="confidence"):
                RangeState(110.0, 100.0, "manual", bad, {}, RangeStatus.VALID)

    def test_is_tradable_requires_valid_positive_width(self) -> None:
        valid = RangeState(110.0, 100.0, "structural", 0.8, {}, RangeStatus.VALID)
        degenerate = RangeState(
            float("nan"), float("nan"), "structural", 0.1, {}, RangeStatus.DEGENERATE
        )
        insufficient = RangeState(
            float("nan"), float("nan"), "atr", 0.0, {}, RangeStatus.INSUFFICIENT_DATA
        )
        assert valid.is_tradable
        assert not degenerate.is_tradable
        assert not insufficient.is_tradable


class TestManualRangeDetector:
    def test_ranging_market_returns_exact_configured_bounds(self) -> None:
        df = make_candles(ranging_closes())
        state = ManualRangeDetector().detect(df, {"range_high": 110.0, "range_low": 100.0})
        assert state.status is RangeStatus.VALID
        assert state.range_high == 110.0
        assert state.range_low == 100.0
        assert state.mode == "manual"
        assert state.confidence == 1.0
        assert state.metadata["source"] == "manual"

    def test_uptrend_content_does_not_affect_result(self) -> None:
        df = make_candles(uptrend_closes())
        state = ManualRangeDetector().detect(df, {"range_high": 150.0, "range_low": 120.0})
        assert (state.range_high, state.range_low) == (150.0, 120.0)

    def test_confidence_override(self) -> None:
        df = make_candles(flat_closes())
        config = {"range_high": 106.0, "range_low": 104.0, "confidence": 0.7}
        state = ManualRangeDetector().detect(df, config)
        assert state.confidence == 0.7

    def test_missing_required_key_raises(self) -> None:
        df = make_candles(ranging_closes())
        with pytest.raises(ValueError, match="range_high"):
            ManualRangeDetector().detect(df, {"range_low": 100.0})

    def test_low_above_high_raises(self) -> None:
        df = make_candles(ranging_closes())
        with pytest.raises(ValueError, match="must not exceed"):
            ManualRangeDetector().detect(df, {"range_high": 90.0, "range_low": 100.0})

    def test_zero_width_is_degenerate(self) -> None:
        df = make_candles(flat_closes())
        state = ManualRangeDetector().detect(df, {"range_high": 105.0, "range_low": 105.0})
        assert state.status is RangeStatus.DEGENERATE
        assert not state.is_tradable
        assert state.confidence == 0.0

    def test_works_on_minimal_frame(self) -> None:
        df = make_candles([100.0])
        state = ManualRangeDetector().detect(df, {"range_high": 101.0, "range_low": 99.0})
        assert state.status is RangeStatus.VALID


class TestVolatilityBollinger:
    def detector(self) -> VolatilityRangeDetector:
        return VolatilityRangeDetector()

    def test_ranging_market_matches_independently_computed_bands(self) -> None:
        closes = ranging_closes()
        df = make_candles(closes)
        state = self.detector().detect(df, {"method": "bollinger", "period": 20, "multiplier": 2.0})
        window = closes[-20:]
        expected_center = float(window.mean())
        expected_std = float(np.std(window, ddof=1))
        assert state.status is RangeStatus.VALID
        assert state.mode == "volatility_bollinger"
        assert state.range_high == pytest.approx(expected_center + 2.0 * expected_std)
        assert state.range_low == pytest.approx(expected_center - 2.0 * expected_std)
        assert state.confidence > 0.3

    def test_uptrend_reports_wide_unconfident_bands(self) -> None:
        df = make_candles(uptrend_closes())
        state = self.detector().detect(df, {"method": "bollinger", "period": 20})
        width = state.range_width
        ranging_width = self.detector().detect(
            make_candles(ranging_closes()), {"method": "bollinger", "period": 20}
        ).range_width
        assert state.status is RangeStatus.VALID
        assert width > ranging_width
        assert state.confidence < 0.5

    def test_insufficient_data_returns_explicit_state(self) -> None:
        df = make_candles([100.0, 101.0, 102.0])
        state = self.detector().detect(df, {"method": "bollinger", "period": 20})
        assert state.status is RangeStatus.INSUFFICIENT_DATA
        assert math.isnan(state.range_high)
        assert state.confidence == 0.0
        assert state.metadata["required_rows"] == 20

    def test_flat_data_is_degenerate_with_zero_volatility_reason(self) -> None:
        df = make_candles(flat_closes())
        state = self.detector().detect(df, {"method": "bollinger", "period": 20})
        assert state.status is RangeStatus.DEGENERATE
        assert state.metadata["reason"] == "zero_volatility"
        assert state.range_high == state.range_low == pytest.approx(105.0)
        assert not state.is_tradable


class TestVolatilityATR:
    def detector(self) -> VolatilityRangeDetector:
        return VolatilityRangeDetector()

    def test_ranging_market_produces_symmetric_channel_around_last_close(self) -> None:
        df = make_candles(ranging_closes())
        state = self.detector().detect(df, {"method": "atr", "period": 14, "multiplier": 1.5})
        assert state.status is RangeStatus.VALID
        assert state.mode == "volatility_atr"
        center = float(state.metadata["center"])
        atr = float(state.metadata["atr"])
        assert center == pytest.approx(105.0 + 5.0 * math.sin((119 * math.pi) / 10.0))
        assert atr > 0.0
        assert state.range_high == pytest.approx(center + 1.5 * atr)
        assert state.range_low == pytest.approx(center - 1.5 * atr)

    def test_larger_multiplier_widens_channel(self) -> None:
        df = make_candles(ranging_closes())
        narrow = self.detector().detect(df, {"method": "atr", "multiplier": 1.0})
        wide = self.detector().detect(df, {"method": "atr", "multiplier": 3.0})
        assert wide.range_width > narrow.range_width

    def test_uptrend_channel_tracks_price_and_scores_low_confidence(self) -> None:
        df = make_candles(uptrend_closes())
        state = self.detector().detect(df, {"method": "atr"})
        last_close = float(df["close"].iloc[-1])
        assert state.status is RangeStatus.VALID
        assert state.range_low < last_close < state.range_high
        assert state.range_width < 0.2 * last_close
        assert state.confidence < 0.5

    def test_insufficient_data_returns_explicit_state(self) -> None:
        df = make_candles([100.0] * 5)
        state = self.detector().detect(df, {"method": "atr", "period": 14})
        assert state.status is RangeStatus.INSUFFICIENT_DATA

    def test_flat_data_is_degenerate(self) -> None:
        df = make_candles(flat_closes(), wiggle=0.0)
        state = self.detector().detect(df, {"method": "atr", "period": 14})
        assert state.status is RangeStatus.DEGENERATE
        assert state.metadata["reason"] == "zero_volatility"
        assert state.range_high == state.range_low == pytest.approx(105.0)

    def test_unknown_method_raises(self) -> None:
        df = make_candles(ranging_closes())
        with pytest.raises(ValueError, match="bollinger.*atr|atr.*bollinger"):
            self.detector().detect(df, {"method": "keltner"})


class TestStructuralRangeDetector:
    def test_ranging_market_detects_accurate_range_with_high_confidence(self) -> None:
        df = make_candles(ranging_closes())
        state = StructuralRangeDetector().detect(df, {"lookback": 120})
        assert state.status is RangeStatus.VALID
        assert state.mode == "structural"
        assert state.range_high > 109.0
        assert state.range_high < 111.0
        assert state.range_low > 99.0
        assert state.range_low < 101.0
        assert state.confidence > 0.65
        assert state.is_tradable
        assert state.metadata["pivot_high_count"] >= 2
        assert state.metadata["pivot_low_count"] >= 2

    def test_clear_uptrend_is_not_reported_as_tradable_range(self) -> None:
        df = make_candles(uptrend_closes())
        state = StructuralRangeDetector().detect(df)
        assert state.status is RangeStatus.DEGENERATE
        assert state.metadata["reason"] == "trending"
        assert state.confidence < 0.3
        assert not state.is_tradable
        assert math.isnan(state.range_high)
        reference_low, reference_high = state.metadata["reference_bounds"]
        assert reference_high > reference_low

    def test_insufficient_data_returns_explicit_state(self) -> None:
        df = make_candles([100.0, 101.0, 102.0, 103.0])
        state = StructuralRangeDetector().detect(df, {"pivot_window": 2})
        assert state.status is RangeStatus.INSUFFICIENT_DATA
        assert state.metadata["required_rows"] == 5

    def test_flat_data_has_no_swing_structure_and_no_fake_range(self) -> None:
        df = make_candles(flat_closes())
        state = StructuralRangeDetector().detect(df)
        assert state.status is RangeStatus.DEGENERATE
        assert state.metadata["reason"] == "no_swing_structure"
        assert state.metadata["pivots_found"] == 0
        assert not state.is_tradable
        assert math.isnan(state.range_high)
        reference_low, reference_high = state.metadata["reference_bounds"]
        assert reference_high == pytest.approx(105.0 + WIGGLE)
        assert reference_low == pytest.approx(105.0 - WIGGLE)

    def test_lookback_limits_analysis_window(self) -> None:
        df = make_candles(ranging_closes(bars=200))
        state = StructuralRangeDetector().detect(df, {"lookback": 50})
        assert state.metadata["lookback"] == 50

    def test_pivot_window_one_recovers_simple_zigzag(self) -> None:
        closes = [100.0, 105.0, 100.0, 95.0, 100.0]
        df = make_candles(closes)
        state = StructuralRangeDetector().detect(df, {"pivot_window": 1, "max_drift_ratio": 1.0})
        assert state.status is RangeStatus.VALID
        assert state.range_high == pytest.approx(105.0 + WIGGLE)
        assert state.range_low == pytest.approx(95.0 - WIGGLE)


class TestOscillatorConfirmedRangeDetector:
    def stub_state(self) -> RangeState:
        return RangeState(
            range_high=110.0,
            range_low=100.0,
            mode="stub",
            confidence=0.9,
            metadata={"base_key": "base_value"},
            status=RangeStatus.VALID,
        )

    def wrapper(self) -> tuple[OscillatorConfirmedRangeDetector, StubDetector]:
        stub = StubDetector(self.stub_state())
        return OscillatorConfirmedRangeDetector(base=stub), stub

    def test_delegates_boundaries_untouched_to_base_detector(self) -> None:
        wrapper, _ = self.wrapper()
        df = make_candles(mid_range_closes())
        state = wrapper.detect(df, {})
        assert (state.range_high, state.range_low) == (110.0, 100.0)
        assert state.mode == "stub"
        assert state.confidence == 0.9
        assert state.status is RangeStatus.VALID
        assert state.metadata["base_key"] == "base_value"

    def test_default_base_detector_is_structural(self) -> None:
        wrapper = OscillatorConfirmedRangeDetector()
        assert isinstance(wrapper.base_detector, StructuralRangeDetector)

    def test_rsi_confirms_at_lower_edge_after_decline_into_floor(self) -> None:
        df = make_candles(decline_into_floor_closes())
        manual = ManualRangeDetector()
        wrapper = OscillatorConfirmedRangeDetector(base=manual)
        state = wrapper.detect(
            df, {"range_high": 110.0, "range_low": 100.0, "oscillator": "rsi"}
        )
        assert state.metadata["confirmation"] is True
        value = float(state.metadata["oscillator_value"])
        assert 0.0 <= value <= 30.0
        assert state.metadata["position_in_range"] == pytest.approx(0.0)
        assert state.metadata["confirmed_by"] == "manual+rsi"

    def test_rsi_confirms_at_upper_edge_after_rally_into_ceiling(self) -> None:
        df = make_candles(rally_into_ceiling_closes())
        manual = ManualRangeDetector()
        wrapper = OscillatorConfirmedRangeDetector(base=manual)
        state = wrapper.detect(
            df, {"range_high": 100.0, "range_low": 90.0, "oscillator": "rsi"}
        )
        assert state.metadata["confirmation"] is True
        assert float(state.metadata["oscillator_value"]) >= 70.0

    def test_mid_range_price_is_not_confirmed(self) -> None:
        df = make_candles(mid_range_closes())
        manual = ManualRangeDetector()
        wrapper = OscillatorConfirmedRangeDetector(base=manual)
        state = wrapper.detect(df, {"range_high": 110.0, "range_low": 100.0, "oscillator": "rsi"})
        assert state.metadata["confirmation"] is False

    def test_stochastic_variant_runs_and_stays_bounded(self) -> None:
        df = make_candles(decline_into_floor_closes())
        manual = ManualRangeDetector()
        wrapper = OscillatorConfirmedRangeDetector(base=manual)
        state = wrapper.detect(
            df, {"range_high": 110.0, "range_low": 100.0, "oscillator": "stoch"}
        )
        value = float(state.metadata["oscillator_value"])
        assert 0.0 <= value <= 100.0
        assert state.metadata["confirmation"] is True

    def test_zero_width_base_range_yields_no_confirmation_without_crash(self) -> None:
        flat_state = RangeState(105.0, 105.0, "stub", 0.0, {}, RangeStatus.DEGENERATE)
        wrapper = OscillatorConfirmedRangeDetector(base=StubDetector(flat_state))
        state = wrapper.detect(make_candles(flat_closes()), {})
        assert state.status is RangeStatus.DEGENERATE
        assert state.metadata["confirmation"] is False
        assert float(state.metadata["oscillator_value"]) == pytest.approx(50.0)

    def test_insufficient_rows_for_oscillator_notes_and_disables_confirmation(self) -> None:
        df = make_candles([100.0, 101.0, 102.0])
        wrapper = OscillatorConfirmedRangeDetector(base=StubDetector(self.stub_state()))
        state = wrapper.detect(df, {"osc_period": 14})
        assert state.metadata["confirmation"] is False
        assert state.metadata["oscillator_note"] == "insufficient_rows_for_oscillator"


class TestRangeEngineFactory:
    def test_defaults_to_structural_when_mode_omitted(self) -> None:
        detector = RangeEngineFactory.create({})
        assert isinstance(detector, StructuralRangeDetector)

    def test_creates_each_registered_mode(self) -> None:
        factory = RangeEngineFactory
        assert isinstance(factory.create({"mode": "manual"}), ManualRangeDetector)
        assert isinstance(factory.create({"mode": "volatility"}), VolatilityRangeDetector)
        assert isinstance(factory.create({"mode": "structural"}), StructuralRangeDetector)

    def test_unknown_mode_raises_with_available_modes(self) -> None:
        with pytest.raises(ValueError, match="structural"):
            RangeEngineFactory.create({"mode": "telepathic"})

    def test_detect_flattens_params_into_effective_config(self) -> None:
        df = make_candles(ranging_closes())
        config: dict[str, object] = {
            "mode": "manual",
            "params": {"range_high": 110.0, "range_low": 100.0},
        }
        state = RangeEngineFactory.detect(df, config)
        assert (state.range_high, state.range_low) == (110.0, 100.0)

    def test_top_level_keys_override_params(self) -> None:
        df = make_candles(ranging_closes())
        config: dict[str, object] = {
            "mode": "manual",
            "params": {"range_high": 110.0, "range_low": 100.0},
            "range_high": 120.0,
        }
        state = RangeEngineFactory.detect(df, config)
        assert state.range_high == 120.0
        assert state.range_low == 100.0

    def test_oscillator_confirmed_nests_base_detector_config(self) -> None:
        config: dict[str, object] = {
            "mode": "oscillator_confirmed",
            "params": {
                "oscillator": "rsi",
                "base": {
                    "mode": "manual",
                    "params": {"range_high": 110.0, "range_low": 100.0},
                },
            },
        }
        detector = RangeEngineFactory.create(config)
        assert isinstance(detector, OscillatorConfirmedRangeDetector)
        assert isinstance(detector.base_detector, ManualRangeDetector)
        df = make_candles(decline_into_floor_closes())
        state = RangeEngineFactory.detect(df, config)
        assert (state.range_high, state.range_low) == (110.0, 100.0)
        assert state.metadata["confirmation"] is True

    def test_available_modes_lists_all_options(self) -> None:
        modes = RangeEngineFactory.available_modes()
        assert set(modes) == {"manual", "volatility", "structural", "oscillator_confirmed"}

    def test_non_string_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="'mode' must be a string"):
            RangeEngineFactory.create({"mode": 42})
