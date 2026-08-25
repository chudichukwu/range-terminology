"""Unit tests for the risk_engine domain package.

All inputs are deterministic synthetic values — no market data, no I/O.
"""

import math

import pytest

from risk_engine import (
    AccountRiskState,
    OpenPosition,
    RejectionReason,
    RiskDecisionStatus,
    RiskEngine,
    StopMethod,
    TargetMethod,
    TradingConstraints,
)
from signal_engine import Signal, SignalDirection, SignalReason

RANGE_HIGH = 110.0
RANGE_LOW = 100.0
EQUITY = 10_000.0


def make_signal(
    direction: SignalDirection = SignalDirection.LONG,
    price: float = 100.5,
) -> Signal:
    """Build a deterministic actionable signal near the lower range edge."""
    reason = (
        SignalReason.SUPPORT_EDGE_SETUP
        if direction is SignalDirection.LONG
        else SignalReason.RESISTANCE_EDGE_SETUP
        if direction is SignalDirection.SHORT
        else SignalReason.PRICE_MID_RANGE
    )
    return Signal(
        direction=direction,
        reason=reason,
        price=price,
        range_high=RANGE_HIGH,
        range_low=RANGE_LOW,
        position_in_range=(price - RANGE_LOW) / (RANGE_HIGH - RANGE_LOW),
        confidence=0.8,
        confirmation=True,
    )


def make_account(**overrides: object) -> AccountRiskState:
    """Build a healthy default account snapshot."""
    values: dict[str, object] = {
        "equity": EQUITY,
        "available_balance": 100_000.0,
        "peak_equity": EQUITY,
        "daily_start_equity": EQUITY,
        "open_positions": (),
        "total_exposure": 0.0,
        "consecutive_losses": 0,
        "realized_pnl": 0.0,
    }
    values.update(overrides)
    return AccountRiskState(**values)  # type: ignore[arg-type]


def make_engine(**config: object) -> RiskEngine:
    """Engine with fees/slippage zeroed unless a test overrides them."""
    base: dict[str, object] = {"fee_rate": 0.0, "slippage_rate": 0.0}
    base.update(config)
    return RiskEngine(base)


class TestModelValidation:
    def test_open_position_rejects_bad_side(self) -> None:
        with pytest.raises(ValueError, match="side"):
            OpenPosition("BTC/USDT", SignalDirection.NONE, 1.0, 100.0)

    def test_open_position_rejects_non_positive_values(self) -> None:
        with pytest.raises(ValueError, match="quantity"):
            OpenPosition("BTC/USDT", SignalDirection.LONG, 0.0, 100.0)
        with pytest.raises(ValueError, match="entry_price"):
            OpenPosition("BTC/USDT", SignalDirection.LONG, 1.0, -5.0)

    def test_open_position_notional(self) -> None:
        pos = OpenPosition("BTC/USDT", SignalDirection.SHORT, 2.0, 50.0)
        assert pos.notional == pytest.approx(100.0)

    def test_account_state_rejects_negative_and_non_finite(self) -> None:
        with pytest.raises(ValueError, match="equity"):
            make_account(equity=-1.0)
        with pytest.raises(ValueError, match="available_balance"):
            make_account(available_balance=float("nan"))
        with pytest.raises(ValueError, match="total_exposure"):
            make_account(total_exposure=float("inf"))
        with pytest.raises(ValueError, match="consecutive_losses"):
            make_account(consecutive_losses=-1)

    def test_constraints_reject_invalid_values(self) -> None:
        with pytest.raises(ValueError, match="quantity_step"):
            TradingConstraints(quantity_step=0.0)
        with pytest.raises(ValueError, match="price_tick"):
            TradingConstraints(price_tick=-0.01)
        with pytest.raises(ValueError, match="max_leverage"):
            TradingConstraints(max_leverage=float("nan"))

    def test_empty_constraints_allowed(self) -> None:
        constraints = TradingConstraints()
        assert constraints.min_quantity is None
        assert constraints.max_leverage is None


class TestSignalGates:
    def setup_method(self) -> None:
        self.engine = make_engine()
        self.account = make_account()

    def test_none_signal_rejected_with_no_signal_reason(self) -> None:
        none_signal = Signal(
            direction=SignalDirection.NONE,
            reason=SignalReason.PRICE_MID_RANGE,
            price=105.0,
            range_high=RANGE_HIGH,
            range_low=RANGE_LOW,
        )
        decision = self.engine.evaluate(none_signal, self.account)
        assert not decision.approved
        assert decision.rejection_reason is RejectionReason.NO_SIGNAL

    def test_direction_reason_mismatch_is_invalid(self) -> None:
        bad = Signal(
            direction=SignalDirection.LONG,
            reason=SignalReason.RESISTANCE_EDGE_SETUP,
            price=109.5,
            range_high=RANGE_HIGH,
            range_low=RANGE_LOW,
        )
        decision = self.engine.evaluate(bad, self.account)
        assert decision.rejection_reason is RejectionReason.INVALID_SIGNAL

    def test_missing_range_bounds_rejected_when_method_needs_them(self) -> None:
        orphan = Signal(
            direction=SignalDirection.LONG,
            reason=SignalReason.SUPPORT_EDGE_SETUP,
            price=100.5,
            confidence=0.8,
        )
        decision = self.engine.evaluate(orphan, self.account)
        assert decision.rejection_reason is RejectionReason.INVALID_SIGNAL
        assert decision.metadata["note"] == "method_requires_range_bounds"

    def test_nan_price_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="finite and positive"):
            self.engine.evaluate(make_signal(), self.account, price=float("nan"))

    def test_zero_price_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="finite and positive"):
            self.engine.evaluate(make_signal(price=0.0), self.account)


class TestAccountGates:
    def setup_method(self) -> None:
        self.engine = make_engine()

    def test_max_account_drawdown_blocks(self) -> None:
        account = make_account(equity=7_500.0, peak_equity=10_000.0)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.rejection_reason is RejectionReason.DRAWDOWN_LIMIT
        assert decision.metadata["drawdown"] == pytest.approx(0.25)

    def test_below_limit_drawdown_passes(self) -> None:
        account = make_account(equity=8_500.0, peak_equity=10_000.0)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.approved or decision.rejection_reason is not RejectionReason.DRAWDOWN_LIMIT

    def test_daily_loss_limit_blocks(self) -> None:
        account = make_account(equity=9_400.0, daily_start_equity=10_000.0)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.rejection_reason is RejectionReason.DAILY_LOSS_LIMIT

    def test_consecutive_loss_limit_blocks(self) -> None:
        account = make_account(consecutive_losses=3)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.rejection_reason is RejectionReason.CONSECUTIVE_LOSS_LIMIT

    def test_max_open_positions_blocks(self) -> None:
        positions = tuple(
            OpenPosition(f"SYM{i}", SignalDirection.LONG, 1.0, 10.0) for i in range(5)
        )
        account = make_account(open_positions=positions)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.rejection_reason is RejectionReason.MAX_OPEN_POSITIONS

    def test_gate_precedence_drawdown_before_sizing(self) -> None:
        account = make_account(equity=6_000.0, peak_equity=10_000.0, consecutive_losses=99)
        decision = self.engine.evaluate(make_signal(), account)
        assert decision.rejection_reason is RejectionReason.DRAWDOWN_LIMIT


class TestStopMethods:
    def test_range_stop_long_below_low_with_buffer(self) -> None:
        engine = make_engine(range_stop_buffer=0.05)
        decision = engine.evaluate(make_signal(price=100.5), make_account())
        assert decision.stop_price == pytest.approx(RANGE_LOW - 0.05 * (RANGE_HIGH - RANGE_LOW))

    def test_range_stop_short_above_high_with_buffer(self) -> None:
        engine = make_engine(range_stop_buffer=0.05)
        decision = engine.evaluate(make_signal(SignalDirection.SHORT, 109.5), make_account())
        assert decision.stop_price == pytest.approx(RANGE_HIGH + 0.05 * (RANGE_HIGH - RANGE_LOW))

    def test_zero_buffer_places_stop_on_boundary(self) -> None:
        engine = make_engine(range_stop_buffer=0.0)
        decision = engine.evaluate(make_signal(price=102.0), make_account())
        assert decision.stop_price == pytest.approx(RANGE_LOW)

    def test_atr_stop_long(self) -> None:
        engine = make_engine(stop_method="atr", atr_multiplier=2.0, min_reward_risk=1.5)
        decision = engine.evaluate(make_signal(price=105.0), make_account(), atr=1.5)
        assert decision.stop_price == pytest.approx(105.0 - 3.0)

    def test_atr_stop_short_mirrored(self) -> None:
        engine = make_engine(stop_method="atr", atr_multiplier=2.0, min_reward_risk=1.5)
        decision = engine.evaluate(
            make_signal(SignalDirection.SHORT, 105.0), make_account(), atr=1.5
        )
        assert decision.stop_price == pytest.approx(105.0 + 3.0)

    def test_fixed_percent_stop(self) -> None:
        engine = make_engine(stop_method="fixed_percent", fixed_stop_percent=0.02)
        decision = engine.evaluate(make_signal(price=100.5), make_account())
        assert decision.stop_price == pytest.approx(100.5 * 0.98)

    def test_atr_required_for_atr_method(self) -> None:
        engine = make_engine(stop_method="atr")
        with pytest.raises(ValueError, match="atr"):
            engine.evaluate(make_signal(price=105.0), make_account())

    def test_non_positive_atr_raises(self) -> None:
        engine = make_engine(stop_method="atr")
        with pytest.raises(ValueError, match="atr"):
            engine.evaluate(make_signal(price=105.0), make_account(), atr=-1.0)

    def test_entry_equal_to_unbuffered_boundary_yields_invalid_stop(self) -> None:
        engine = make_engine(range_stop_buffer=0.0)
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.rejection_reason is RejectionReason.INVALID_STOP


class TestTargetsAndRewardRisk:
    def test_opposite_edge_target_long(self) -> None:
        decision = make_engine().evaluate(make_signal(price=100.5), make_account())
        assert decision.target_price == pytest.approx(RANGE_HIGH)

    def test_opposite_edge_target_short(self) -> None:
        decision = make_engine().evaluate(
            make_signal(SignalDirection.SHORT, 109.5), make_account()
        )
        assert decision.target_price == pytest.approx(RANGE_LOW)

    def test_range_fraction_target(self) -> None:
        engine = make_engine(target_method="range_fraction", range_target_fraction=0.9)
        long_decision = engine.evaluate(make_signal(price=100.5), make_account())
        short_decision = engine.evaluate(
            make_signal(SignalDirection.SHORT, 109.5), make_account()
        )
        assert long_decision.target_price == pytest.approx(RANGE_LOW + 0.9 * 10.0)
        assert short_decision.target_price == pytest.approx(RANGE_HIGH - 0.9 * 10.0)

    def test_fixed_rr_target(self) -> None:
        engine = make_engine(
            stop_method="fixed_percent",
            fixed_stop_percent=0.02,
            target_method="fixed_rr",
            fixed_rr_ratio=3.0,
        )
        entry = 100.0
        decision = engine.evaluate(make_signal(price=entry), make_account())
        stop_distance = entry * 0.02
        assert decision.target_price == pytest.approx(entry + 3.0 * stop_distance)

    def test_reward_risk_ratio_calculation_fee_free(self) -> None:
        engine = make_engine(
            stop_method="fixed_percent",
            fixed_stop_percent=0.02,
            target_method="fixed_rr",
            fixed_rr_ratio=3.0,
        )
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.reward_risk_ratio == pytest.approx(3.0)
        assert decision.potential_loss == pytest.approx(decision.position_quantity * 2.0)
        assert decision.potential_reward == pytest.approx(decision.position_quantity * 6.0)

    def test_min_reward_risk_rejection(self) -> None:
        engine = make_engine(
            stop_method="fixed_percent",
            fixed_stop_percent=0.05,
            target_method="fixed_rr",
            fixed_rr_ratio=1.5,
            min_reward_risk=2.0,
        )
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.rejection_reason is RejectionReason.MIN_REWARD_RISK
        assert decision.metadata["reward_risk_ratio"] == pytest.approx(1.5)

    def test_fees_reduce_reward_risk(self) -> None:
        base: dict[str, object] = {
            "stop_method": "fixed_percent",
            "fixed_stop_percent": 0.02,
            "target_method": "fixed_rr",
            "fixed_rr_ratio": 3.0,
            "min_reward_risk": 1.0,
        }
        clean = make_engine(**base)
        costly = make_engine(**base, fee_rate=0.005, slippage_rate=0.002)
        clean_decision = clean.evaluate(make_signal(price=100.0), make_account())
        costly_decision = costly.evaluate(make_signal(price=100.0), make_account())
        assert costly_decision.approved
        assert costly_decision.reward_risk_ratio < clean_decision.reward_risk_ratio
        assert costly_decision.fees_estimate > 0.0
        assert costly_decision.slippage_estimate > 0.0


class TestPositionSizing:
    def test_percentage_of_equity_sizing(self) -> None:
        decision = make_engine().evaluate(make_signal(price=100.0), make_account())
        expected_risk = EQUITY * 0.01
        stop_distance = 100.0 - (RANGE_LOW - 0.05 * 10.0)
        assert decision.risk_amount == pytest.approx(expected_risk)
        assert decision.requested_quantity == pytest.approx(expected_risk / stop_distance)

    def test_risk_percentage_is_not_size_percentage(self) -> None:
        decision = make_engine().evaluate(make_signal(price=100.0), make_account())
        stop_distance = 100.0 - (RANGE_LOW - 0.05 * (RANGE_HIGH - RANGE_LOW))
        assert decision.position_notional != pytest.approx(EQUITY * 0.01)
        assert decision.risk_amount == pytest.approx(EQUITY * 0.01)
        assert float(decision.position_quantity) * stop_distance == pytest.approx(
            EQUITY * 0.01
        )

    def test_equity_scales_quantity_linearly(self) -> None:
        small = make_engine().evaluate(
            make_signal(price=100.0),
            make_account(equity=5_000.0, peak_equity=5_000.0, daily_start_equity=5_000.0),
        )
        large = make_engine().evaluate(
            make_signal(price=100.0),
            make_account(equity=20_000.0, peak_equity=20_000.0, daily_start_equity=20_000.0),
        )
        assert small.approved and large.approved
        assert float(large.requested_quantity) == pytest.approx(
            4.0 * float(small.requested_quantity)
        )

    def test_long_short_symmetry(self) -> None:
        engine = make_engine()
        long_decision = engine.evaluate(make_signal(SignalDirection.LONG, 102.0), make_account())
        short_decision = engine.evaluate(
            make_signal(SignalDirection.SHORT, 108.0), make_account()
        )
        long_distance = 102.0 - (RANGE_LOW - 0.5)
        short_distance = (RANGE_HIGH + 0.5) - 108.0
        scale = long_distance / short_distance
        assert long_decision.position_quantity == pytest.approx(
            float(short_decision.position_quantity) * scale
        )
        assert long_decision.reward_risk_ratio == pytest.approx(short_decision.reward_risk_ratio)
        assert long_decision.potential_loss == pytest.approx(short_decision.potential_loss)

    def test_deterministic_repeated_evaluation(self) -> None:
        engine = make_engine()
        first = engine.evaluate(make_signal(price=100.5), make_account())
        second = engine.evaluate(make_signal(price=100.5), make_account())
        assert first == second


class TestLimitsAndCaps:
    def test_max_position_notional_cap(self) -> None:
        engine = make_engine(max_position_notional=1_000.0)
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.approved
        assert decision.position_notional <= 1_000.0 + 1e-9
        assert decision.metadata["binding_constraint"] == "position_size"
        assert float(decision.position_quantity) < float(decision.requested_quantity)

    def test_max_portfolio_exposure_caps_remaining_room(self) -> None:
        existing = OpenPosition("ETH/USDT", SignalDirection.LONG, 10.0, 900.0)
        engine = make_engine(max_total_exposure=10_000.0)
        account = make_account(
            open_positions=(existing,), total_exposure=9_500.0, available_balance=20_000.0
        )
        decision = engine.evaluate(make_signal(price=100.0), account)
        assert decision.approved
        assert decision.position_notional <= 500.0 + 1e-9
        assert decision.metadata["binding_constraint"] == "portfolio_exposure"

    def test_portfolio_exposure_exhausted_rejects(self) -> None:
        engine = make_engine(max_total_exposure=10_000.0)
        account = make_account(total_exposure=10_000.0)
        decision = engine.evaluate(make_signal(price=100.0), account)
        assert decision.rejection_reason is RejectionReason.MAX_PORTFOLIO_EXPOSURE

    def test_asset_exposure_cap_scoped_by_symbol(self) -> None:
        btc_position = OpenPosition("BTC/USDT", SignalDirection.LONG, 1.0, 60_000.0)
        eth_position = OpenPosition("ETH/USDT", SignalDirection.SHORT, 1.0, 3_000.0)
        engine = make_engine(max_asset_exposure=60_000.0)
        account = make_account(
            open_positions=(btc_position, eth_position),
            total_exposure=63_000.0,
            available_balance=200_000.0,
        )
        blocked = engine.evaluate(make_signal(price=100.0), account, symbol="BTC/USDT")
        allowed = engine.evaluate(make_signal(price=100.0), account, symbol="ETH/USDT")
        assert blocked.rejection_reason is RejectionReason.MAX_PORTFOLIO_EXPOSURE
        assert blocked.metadata["binding_constraint"] == "asset_exposure"
        assert allowed.approved

    def test_funding_shortfall_rejects_rather_than_downsizes(self) -> None:
        engine = make_engine(max_leverage=1.0)
        account = make_account(available_balance=5_000.0)
        decision = engine.evaluate(make_signal(price=100.0), account)
        assert decision.rejection_reason is RejectionReason.INSUFFICIENT_BALANCE

    def test_higher_configured_leverage_enables_the_trade(self) -> None:
        tight = make_engine(max_leverage=1.0)
        loose = make_engine(max_leverage=5.0)
        account = make_account(available_balance=5_000.0)
        tight_decision = tight.evaluate(make_signal(price=100.0), account)
        loose_decision = loose.evaluate(make_signal(price=100.0), account)
        assert not tight_decision.approved
        assert loose_decision.approved
        assert loose_decision.risk_amount == EQUITY * 0.01
        assert float(loose_decision.position_notional) > 5_000.0

    def test_insufficient_balance_rejected(self) -> None:
        engine = make_engine(max_leverage=1.0)
        account = make_account(available_balance=10.0)
        decision = engine.evaluate(make_signal(price=100.0), account)
        assert decision.rejection_reason is RejectionReason.INSUFFICIENT_BALANCE

    def test_leverage_limit_from_constraints(self) -> None:
        engine = make_engine(max_leverage=5.0)
        constraints = TradingConstraints(max_leverage=2.0)
        account = make_account(available_balance=4_000.0)
        decision = engine.evaluate(make_signal(price=100.0), account, constraints=constraints)
        assert decision.rejection_reason is RejectionReason.LEVERAGE_LIMIT

    def test_zero_balance_rejected_as_insufficient(self) -> None:
        engine = make_engine(max_leverage=5.0)
        decision = engine.evaluate(make_signal(price=100.0), make_account(available_balance=0.0))
        assert decision.rejection_reason is RejectionReason.INSUFFICIENT_BALANCE


class TestExchangeConstraints:
    def make_engine_and_account(self) -> tuple[RiskEngine, AccountRiskState]:
        engine = make_engine(max_position_notional=100_000.0)
        return engine, make_account(available_balance=200_000.0)

    def test_min_quantity_rejects_dust(self) -> None:
        engine, account = self.make_engine_and_account()
        constraints = TradingConstraints(min_quantity=1_000_000.0)
        decision = engine.evaluate(make_signal(price=100.0), account, constraints=constraints)
        assert decision.rejection_reason is RejectionReason.EXCHANGE_CONSTRAINT
        assert decision.metadata["note"] == "quantity_below_min"

    def test_max_quantity_clamps(self) -> None:
        engine, account = self.make_engine_and_account()
        constraints = TradingConstraints(max_quantity=5.0)
        decision = engine.evaluate(make_signal(price=100.0), account, constraints=constraints)
        assert decision.approved
        assert decision.metadata["constraints_applied"] == ["max_quantity_clamp"]
        assert float(decision.position_quantity) <= 5.0

    def test_quantity_step_rounds_down(self) -> None:
        engine, account = self.make_engine_and_account()
        constraints = TradingConstraints(quantity_step=0.3)
        decision = engine.evaluate(make_signal(price=100.0), account, constraints=constraints)
        quantity = float(decision.position_quantity)
        assert quantity == pytest.approx(math.floor(quantity / 0.3 + 1e-12) * 0.3, rel=1e-9)
        assert decision.metadata["constraints_applied"] == ["quantity_step_rounding"]

    def test_min_notional_rejects(self) -> None:
        engine, _ = self.make_engine_and_account()
        tiny = make_engine(max_position_notional=10.0)
        decision = tiny.evaluate(
            make_signal(price=100.0),
            make_account(),
            constraints=TradingConstraints(min_notional=100.0),
        )
        assert decision.rejection_reason is RejectionReason.EXCHANGE_CONSTRAINT
        assert decision.metadata["note"] == "notional_below_min"

    def test_price_tick_rounds_stop_away_and_target_toward_entry(self) -> None:
        engine = make_engine(max_position_notional=100_000.0)
        account = make_account(available_balance=200_000.0)
        constraints = TradingConstraints(price_tick=0.4)
        long_decision = engine.evaluate(
            make_signal(SignalDirection.LONG, 101.3), account, constraints=constraints
        )
        assert long_decision.approved
        assert long_decision.stop_price == pytest.approx(99.6)
        assert long_decision.target_price == pytest.approx(110.0)

    def test_absent_constraints_invent_nothing(self) -> None:
        engine, account = self.make_engine_and_account()
        decision = engine.evaluate(make_signal(price=100.0), account, constraints=None)
        assert decision.metadata["constraints_applied"] == []
        assert decision.stop_price == pytest.approx(RANGE_LOW - 0.5)


class TestConfigurationValidation:
    def test_risk_per_trade_bounds(self) -> None:
        with pytest.raises(ValueError, match="risk_per_trade"):
            RiskEngine({"risk_per_trade": 0.0})
        with pytest.raises(ValueError, match="risk_per_trade"):
            RiskEngine({"risk_per_trade": 1.5})

    def test_invalid_stop_method_raises(self) -> None:
        with pytest.raises(ValueError, match="stop_method"):
            RiskEngine({"stop_method": "vibes"})

    def test_invalid_target_method_raises(self) -> None:
        with pytest.raises(ValueError, match="target_method"):
            RiskEngine({"target_method": "moon"})

    def test_negative_fee_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="fee_rate"):
            RiskEngine({"fee_rate": -0.001})

    def test_invalid_drawdown_limits_raise(self) -> None:
        with pytest.raises(ValueError, match="max_drawdown"):
            RiskEngine({"max_drawdown": 0.0})
        with pytest.raises(ValueError, match="max_daily_drawdown"):
            RiskEngine({"max_daily_drawdown": 1.0})

    def test_unknown_keys_are_ignored(self) -> None:
        engine = RiskEngine({"totally_unknown_key": 42})
        assert isinstance(engine, RiskEngine)

    def test_stop_method_enum_roundtrip(self) -> None:
        engine = RiskEngine({"stop_method": "fixed_percent"})
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.metadata["stop_method"] == StopMethod.FIXED_PERCENT.value

    def test_target_method_enum_roundtrip(self) -> None:
        engine = RiskEngine({"target_method": "opposite_range_edge"})
        decision = engine.evaluate(make_signal(price=100.0), make_account())
        assert decision.metadata["target_method"] == TargetMethod.OPPOSITE_RANGE_EDGE.value

    def test_approved_decision_shape(self) -> None:
        decision = make_engine().evaluate(make_signal(price=100.5), make_account())
        assert decision.status is RiskDecisionStatus.APPROVED
        assert decision.rejection_reason is None
        assert math.isfinite(float(decision.position_quantity))
        assert float(decision.potential_reward) > 0.0
        assert float(decision.potential_loss) > 0.0
