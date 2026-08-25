"""Unit tests for the signal_engine domain package.

All inputs are deterministic synthetic values — no market data, no I/O.
"""


import numpy as np
import pandas as pd
import pytest

from range_engine import (
    ManualRangeDetector,
    OscillatorConfirmedRangeDetector,
    RangeState,
    RangeStatus,
)
from signal_engine import (
    RangeSignalEngine,
    Signal,
    SignalDirection,
    SignalReason,
)


def make_range_state(
    range_high: float = 110.0,
    range_low: float = 100.0,
    *,
    status: RangeStatus = RangeStatus.VALID,
    confidence: float = 0.8,
    mode: str = "structural",
    metadata: dict[str, object] | None = None,
) -> RangeState:
    """Build a deterministic RangeState for signal evaluation tests."""
    return RangeState(
        range_high=range_high,
        range_low=range_low,
        mode=mode,
        confidence=confidence,
        metadata=dict(metadata or {}),
        status=status,
    )


def make_candles(closes: list[float] | np.ndarray) -> pd.DataFrame:
    """Build a deterministic OHLCV frame (same construction as range tests)."""
    close_arr = np.asarray(closes, dtype=float)
    open_arr = np.concatenate(([close_arr[0]], close_arr[:-1]))
    timestamps = pd.date_range("2024-01-01", periods=len(close_arr), freq="1h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_arr,
            "high": np.maximum(open_arr, close_arr) + 0.25,
            "low": np.minimum(open_arr, close_arr) - 0.25,
            "close": close_arr,
            "volume": 1000.0,
        }
    )


def confirmed_state(confirmed: bool) -> RangeState:
    """Tradable state carrying oscillator confirmation metadata."""
    return make_range_state(
        metadata={"confirmation": confirmed, "oscillator_value": 25.0 if confirmed else 55.0}
    )


class TestSignalModel:
    def test_signal_is_immutable(self) -> None:
        signal = Signal(SignalDirection.LONG, SignalReason.SUPPORT_EDGE_SETUP, price=100.0)
        with pytest.raises(AttributeError):
            signal.direction = SignalDirection.SHORT  # type: ignore[misc]

    def test_is_actionable_distinguishes_setup_from_no_signal(self) -> None:
        long_signal = Signal(SignalDirection.LONG, SignalReason.SUPPORT_EDGE_SETUP, price=100.0)
        none_signal = Signal(SignalDirection.NONE, SignalReason.PRICE_MID_RANGE, price=105.0)
        assert long_signal.is_actionable
        assert not none_signal.is_actionable


class TestNonTradableGate:
    def test_degenerate_state_yields_none(self) -> None:
        state = make_range_state(
            status=RangeStatus.DEGENERATE,
            metadata={"reason": "trending"},
        )
        signal = RangeSignalEngine().evaluate(101.0, state)
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.NON_TRADABLE_RANGE
        assert not signal.is_actionable
        assert signal.metadata["range_reason"] == "trending"
        assert signal.position_in_range is None

    def test_insufficient_data_state_yields_none(self) -> None:
        state = make_range_state(
            status=RangeStatus.INSUFFICIENT_DATA,
            confidence=0.0,
            metadata={"reason": "insufficient_data"},
        )
        signal = RangeSignalEngine().evaluate(105.0, state)
        assert signal.reason is SignalReason.NON_TRADABLE_RANGE
        assert signal.metadata["range_status"] == "insufficient_data"

    def test_zero_width_valid_status_still_gated(self) -> None:
        state = make_range_state(range_high=105.0, range_low=105.0)
        assert not state.is_tradable
        signal = RangeSignalEngine().evaluate(104.9, state)
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.NON_TRADABLE_RANGE

    def test_nan_bounds_state_gated_without_crash(self) -> None:
        state = make_range_state(
            range_high=float("nan"),
            range_low=float("nan"),
            status=RangeStatus.INSUFFICIENT_DATA,
            metadata={"reason": "insufficient_data"},
        )
        signal = RangeSignalEngine().evaluate(105.0, state)
        assert signal.range_high is None
        assert signal.range_low is None


class TestZoneClassification:
    def setup_method(self) -> None:
        self.engine = RangeSignalEngine({"confirmation_policy": "ignored"})
        self.state = make_range_state()

    def test_price_at_lower_boundary_longs(self) -> None:
        signal = self.engine.evaluate(100.0, self.state)
        assert signal.direction is SignalDirection.LONG
        assert signal.reason is SignalReason.SUPPORT_EDGE_SETUP
        assert signal.position_in_range == pytest.approx(0.0)

    def test_price_at_upper_boundary_shorts(self) -> None:
        signal = self.engine.evaluate(110.0, self.state)
        assert signal.direction is SignalDirection.SHORT
        assert signal.reason is SignalReason.RESISTANCE_EDGE_SETUP
        assert signal.position_in_range == pytest.approx(1.0)

    def test_price_inside_lower_zone_longs(self) -> None:
        signal = self.engine.evaluate(102.0, self.state)
        assert signal.direction is SignalDirection.LONG

    def test_price_inside_upper_zone_shorts(self) -> None:
        signal = self.engine.evaluate(108.5, self.state)
        assert signal.direction is SignalDirection.SHORT

    def test_price_mid_range_is_no_signal_with_context(self) -> None:
        signal = self.engine.evaluate(106.0, self.state)
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.PRICE_MID_RANGE
        assert signal.range_high == pytest.approx(110.0)
        assert signal.range_low == pytest.approx(100.0)
        assert signal.position_in_range == pytest.approx(0.6)

    def test_price_below_range_is_no_signal_not_error(self) -> None:
        signal = self.engine.evaluate(95.0, self.state)
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.PRICE_OUTSIDE_RANGE
        assert signal.position_in_range == pytest.approx(-0.5)

    def test_price_above_range_is_no_signal_not_error(self) -> None:
        signal = self.engine.evaluate(115.0, self.state)
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.PRICE_OUTSIDE_RANGE
        assert signal.position_in_range == pytest.approx(1.5)

    def test_exact_lower_zone_edge_is_inclusive_long(self) -> None:
        signal = self.engine.evaluate(102.5, self.state)
        assert signal.position_in_range == pytest.approx(0.25)
        assert signal.direction is SignalDirection.LONG

    def test_exact_upper_zone_edge_is_inclusive_short(self) -> None:
        signal = self.engine.evaluate(107.5, self.state)
        assert signal.position_in_range == pytest.approx(0.75)
        assert signal.direction is SignalDirection.SHORT

    def test_just_outside_zone_edges_fall_to_mid_range(self) -> None:
        below_zone = self.engine.evaluate(102.5001, self.state)
        above_zone = self.engine.evaluate(107.4999, self.state)
        assert below_zone.reason is SignalReason.PRICE_MID_RANGE
        assert above_zone.reason is SignalReason.PRICE_MID_RANGE

    def test_asymmetric_zones_respected(self) -> None:
        engine = RangeSignalEngine(
            {"lower_edge_zone": 0.2, "upper_edge_zone": 0.3, "confirmation_policy": "ignored"}
        )
        at_old_lower_edge = engine.evaluate(102.4, self.state)
        in_upper_zone = engine.evaluate(107.0, self.state)
        between_zones = engine.evaluate(103.0, self.state)
        assert at_old_lower_edge.reason is SignalReason.PRICE_MID_RANGE
        assert in_upper_zone.direction is SignalDirection.SHORT
        assert between_zones.reason is SignalReason.PRICE_MID_RANGE


class TestConfirmationPolicy:
    def setup_method(self) -> None:
        self.engine_required = RangeSignalEngine({"confirmation_policy": "required"})
        self.state = make_range_state()

    def test_required_passing_confirmation_produces_actionable_signal(self) -> None:
        signal = self.engine_required.evaluate(100.5, confirmed_state(True))
        assert signal.is_actionable
        assert signal.direction is SignalDirection.LONG
        assert signal.confirmation is True
        assert signal.metadata["confirmation_source"] == "oscillator"

    def test_required_false_confirmation_blocks_setup(self) -> None:
        signal = self.engine_required.evaluate(109.5, confirmed_state(False))
        assert not signal.is_actionable
        assert signal.reason is SignalReason.CONFIRMATION_NOT_MET
        assert signal.confirmation is False
        assert signal.metadata["blocked_by"] == "confirmation"

    def test_required_missing_confirmation_blocks_setup(self) -> None:
        signal = self.engine_required.evaluate(100.5, make_range_state())
        assert signal.reason is SignalReason.CONFIRMATION_NOT_MET
        assert signal.confirmation is None
        assert signal.metadata["confirmation_present"] is False
        assert signal.metadata["blocked_by"] == "confirmation"

    def test_malformed_confirmation_treated_as_missing(self) -> None:
        state = make_range_state(metadata={"confirmation": "yes"})
        signal = self.engine_required.evaluate(100.5, state)
        assert signal.reason is SignalReason.CONFIRMATION_NOT_MET
        assert signal.metadata["confirmation_present"] is False

    def test_optional_policy_surfaces_but_never_blocks(self) -> None:
        engine = RangeSignalEngine({"confirmation_policy": "optional"})
        passing = engine.evaluate(100.5, confirmed_state(True))
        failing = engine.evaluate(100.5, confirmed_state(False))
        absent = engine.evaluate(100.5, make_range_state())
        assert passing.is_actionable and passing.confirmation is True
        assert failing.is_actionable and failing.confirmation is False
        assert absent.is_actionable and absent.confirmation is None

    def test_ignored_policy_never_reads_confirmation(self) -> None:
        engine = RangeSignalEngine({"confirmation_policy": "ignored"})
        signal = engine.evaluate(109.5, confirmed_state(False))
        assert signal.is_actionable
        assert signal.direction is SignalDirection.SHORT
        assert signal.confirmation is None
        assert signal.metadata["confirmation_source"] == "ignored"
        assert "oscillator_value" not in signal.metadata


class TestSymmetryAndConfidence:
    def setup_method(self) -> None:
        self.engine = RangeSignalEngine({"confirmation_policy": "required"})

    def test_long_and_short_symmetry(self) -> None:
        state = confirmed_state(True)
        long_signal = self.engine.evaluate(100.0, state)
        short_signal = self.engine.evaluate(110.0, state)
        assert long_signal.direction is SignalDirection.LONG
        assert short_signal.direction is SignalDirection.SHORT
        assert long_signal.reason is SignalReason.SUPPORT_EDGE_SETUP
        assert short_signal.reason is SignalReason.RESISTANCE_EDGE_SETUP
        assert long_signal.confidence == short_signal.confidence > 0.0
        assert long_signal.position_in_range == pytest.approx(
            1.0 - float(short_signal.position_in_range)
        )

    def test_confidence_rises_toward_boundary(self) -> None:
        state = make_range_state(confidence=0.8)
        engine = RangeSignalEngine({"confirmation_policy": "ignored"})
        shallow = engine.evaluate(102.3, state)
        deep = engine.evaluate(100.0, state)
        assert shallow.is_actionable and deep.is_actionable
        assert deep.confidence > shallow.confidence
        assert shallow.confidence < 0.8 <= deep.confidence

    def test_confidence_scales_with_range_confidence(self) -> None:
        weak_range = make_range_state(confidence=0.3)
        strong_range = make_range_state(confidence=0.9)
        engine = RangeSignalEngine({"confirmation_policy": "ignored"})
        assert engine.evaluate(100.0, weak_range).confidence < engine.evaluate(
            100.0, strong_range
        ).confidence

    def test_repeated_evaluation_is_deterministic(self) -> None:
        state = confirmed_state(True)
        first = self.engine.evaluate(100.25, state)
        second = self.engine.evaluate(100.25, state)
        assert first == second


class TestConfigurationValidation:
    def test_zero_edge_zone_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_edge_zone"):
            RangeSignalEngine({"lower_edge_zone": 0.0})

    def test_oversized_edge_zone_raises(self) -> None:
        with pytest.raises(ValueError, match="upper_edge_zone"):
            RangeSignalEngine({"upper_edge_zone": 0.6})

    def test_negative_edge_zone_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_edge_zone"):
            RangeSignalEngine({"lower_edge_zone": -0.1})

    def test_touching_half_zones_are_valid(self) -> None:
        engine = RangeSignalEngine(
            {"lower_edge_zone": 0.5, "upper_edge_zone": 0.5, "confirmation_policy": "ignored"}
        )
        signal = engine.evaluate(105.0, make_range_state())
        assert signal.direction is SignalDirection.LONG

    def test_unknown_policy_raises_listing_options(self) -> None:
        engine = RangeSignalEngine()
        state = make_range_state()
        with pytest.raises(ValueError, match="required.*optional.*ignored|optional.*required"):
            engine.evaluate(105.0, state, {"confirmation_policy": "yolo"})

    def test_non_numeric_zone_raises(self) -> None:
        with pytest.raises(ValueError, match="lower_edge_zone"):
            RangeSignalEngine({"lower_edge_zone": "wide"})


class TestPriceValidation:
    def setup_method(self) -> None:
        self.engine = RangeSignalEngine()
        self.state = make_range_state()

    def test_nan_price_raises(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            self.engine.evaluate(float("nan"), self.state)

    def test_infinite_price_raises(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            self.engine.evaluate(float("inf"), self.state)

    def test_string_price_raises(self) -> None:
        with pytest.raises(ValueError, match="real number"):
            self.engine.evaluate("100.0", self.state)  # type: ignore[arg-type]

    def test_bool_price_raises(self) -> None:
        with pytest.raises(ValueError, match="real number"):
            self.engine.evaluate(True, self.state)  # type: ignore[arg-type]


class TestPerCallOverrides:
    def test_call_config_overrides_constructor_defaults(self) -> None:
        engine = RangeSignalEngine({"confirmation_policy": "ignored", "lower_edge_zone": 0.25})
        state = make_range_state()
        default_run = engine.evaluate(102.0, state)
        narrowed = engine.evaluate(102.0, state, {"lower_edge_zone": 0.1})
        assert default_run.direction is SignalDirection.LONG
        assert narrowed.reason is SignalReason.PRICE_MID_RANGE

    def test_constructor_instance_reusable_across_calls(self) -> None:
        engine = RangeSignalEngine()
        first = engine.evaluate(100.5, make_range_state())
        second = engine.evaluate(100.5, make_range_state())
        assert first == second


class TestRangeEngineIntegration:
    def test_full_pipeline_through_oscillator_wrapper(self) -> None:
        closes = np.concatenate((np.linspace(200.0, 100.0, 30), np.full(6, 100.0)))
        df = make_candles(closes)
        detector = OscillatorConfirmedRangeDetector(base=ManualRangeDetector())
        state = detector.detect(df, {"range_high": 110.0, "range_low": 100.0})
        assert state.metadata["confirmation"] is True
        engine = RangeSignalEngine({"confirmation_policy": "required"})
        signal = engine.evaluate(float(df["close"].iloc[-1]), state)
        assert signal.is_actionable
        assert signal.direction is SignalDirection.LONG
        assert signal.confirmation is True
        assert signal.metadata["oscillator_value"] == state.metadata["oscillator_value"]
        assert 0.0 <= signal.confidence <= 1.0

    def test_structural_uptrend_state_produces_no_signal(self) -> None:
        from range_engine import StructuralRangeDetector

        df = make_candles((100.0 + 0.6 * np.arange(150)).tolist())
        state = StructuralRangeDetector().detect(df)
        assert state.status is RangeStatus.DEGENERATE
        signal = RangeSignalEngine({"confirmation_policy": "required"}).evaluate(
            float(df["close"].iloc[-1]), state
        )
        assert signal.direction is SignalDirection.NONE
        assert signal.reason is SignalReason.NON_TRADABLE_RANGE
