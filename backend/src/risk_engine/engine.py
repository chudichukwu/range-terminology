"""Risk evaluation engine: Signal + AccountRiskState -> RiskDecision.

Pure domain logic answering "is this trade allowed, and with which size,
stop, target and risk parameters?". Never places orders, never touches I/O.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from range_engine.base import get_choice, get_float, get_int
from risk_engine.base import (
    AccountRiskState,
    RejectionReason,
    RiskDecision,
    RiskDecisionStatus,
    StopMethod,
    TargetMethod,
    TradingConstraints,
)
from signal_engine import Signal, SignalDirection, SignalReason

_DEFAULTS: dict[str, object] = {
    "risk_per_trade": 0.01,
    "stop_method": "range",
    "range_stop_buffer": 0.05,
    "atr_multiplier": 2.0,
    "fixed_stop_percent": 0.02,
    "target_method": "opposite_range_edge",
    "range_target_fraction": 0.9,
    "fixed_rr_ratio": 3.0,
    "min_reward_risk": 2.0,
    "max_drawdown": 0.20,
    "max_daily_drawdown": 0.05,
    "max_consecutive_losses": 3,
    "max_open_positions": 5,
    "max_leverage": 1.0,
    "fee_rate": 0.001,
    "slippage_rate": 0.0005,
}


def _get_optional_positive(cfg: Mapping[str, object], key: str) -> float | None:
    """Read an optional strictly-positive float config value (None passthrough)."""
    if cfg.get(key) is None:
        return None
    return get_float(cfg, key)


@dataclass(frozen=True)
class RiskParams:
    """Typed, validated snapshot of the effective risk configuration."""

    risk_per_trade: float
    stop_method: StopMethod
    range_stop_buffer: float
    atr_multiplier: float
    fixed_stop_percent: float
    target_method: TargetMethod
    range_target_fraction: float
    fixed_rr_ratio: float
    min_reward_risk: float
    max_drawdown: float
    max_daily_drawdown: float
    max_consecutive_losses: int
    max_open_positions: int
    max_position_notional: float | None
    max_total_exposure: float | None
    max_asset_exposure: float | None
    max_leverage: float
    fee_rate: float
    slippage_rate: float


class RiskEngine:
    """Approves or rejects trading signals and shapes approved trades.

    The primary risk model is percentage-of-equity: ``risk_amount = equity x
    risk_per_trade``; quantity follows from stop distance, then is shaped by
    balance/leverage funding, notional/exposure caps and optional venue
    constraints. Drawdown, daily-loss, consecutive-loss and open-position
    gates run before sizing. Fee and slippage estimates feed reward/risk
    economics and are exposed explicitly on every decision. Leverage never
    increases the risk amount — it only affects how much notional the
    available balance can fund. Calculations are deterministic and
    LONG/SHORT symmetric.
    """

    def __init__(self, config: Mapping[str, object] | None = None) -> None:
        """Store and validate default configuration.

        Args:
            config: Same keys as accepted by :meth:`evaluate`; per-call config
                overrides these defaults.

        Raises:
            ValueError: On invalid configuration values.
        """
        self._config: dict[str, object] = {**_DEFAULTS, **dict(config or {})}
        self._resolve_params(self._config)

    @staticmethod
    def _resolve_params(cfg: Mapping[str, object]) -> RiskParams:
        """Validate configuration and build the typed parameter snapshot."""
        risk_per_trade = get_float(cfg, "risk_per_trade")
        if not 0.0 < risk_per_trade <= 1.0:
            raise ValueError(
                f"Config key 'risk_per_trade' must be within (0, 1], got {risk_per_trade}"
            )
        for key in ("min_reward_risk", "fixed_rr_ratio", "atr_multiplier", "max_leverage"):
            if get_float(cfg, key) <= 0.0:
                raise ValueError(f"Config key {key!r} must be positive")
        for key in ("fee_rate", "slippage_rate"):
            if get_float(cfg, key) < 0.0:
                raise ValueError(f"Config key {key!r} must be non-negative")
        for key in ("max_drawdown", "max_daily_drawdown"):
            value = get_float(cfg, key)
            if not 0.0 < value < 1.0:
                raise ValueError(f"Config key {key!r} must be within (0, 1), got {value}")
        buffer_fraction = get_float(cfg, "range_stop_buffer", minimum=0.0)
        if buffer_fraction >= 1.0:
            raise ValueError(
                f"Config key 'range_stop_buffer' must be below 1.0, got {buffer_fraction}"
            )
        fraction = get_float(cfg, "range_target_fraction")
        if not 0.0 < fraction <= 1.0:
            raise ValueError(
                f"Config key 'range_target_fraction' must be within (0, 1], got {fraction}"
            )
        stop_modes = tuple(m.value for m in StopMethod)
        return RiskParams(
            risk_per_trade=risk_per_trade,
            stop_method=StopMethod(get_choice(cfg, "stop_method", stop_modes)),
            range_stop_buffer=buffer_fraction,
            atr_multiplier=get_float(cfg, "atr_multiplier"),
            fixed_stop_percent=get_float(cfg, "fixed_stop_percent"),
            target_method=TargetMethod(
                get_choice(cfg, "target_method", tuple(m.value for m in TargetMethod))
            ),
            range_target_fraction=fraction,
            fixed_rr_ratio=get_float(cfg, "fixed_rr_ratio"),
            min_reward_risk=get_float(cfg, "min_reward_risk"),
            max_drawdown=get_float(cfg, "max_drawdown"),
            max_daily_drawdown=get_float(cfg, "max_daily_drawdown"),
            max_consecutive_losses=get_int(cfg, "max_consecutive_losses", minimum=0),
            max_open_positions=get_int(cfg, "max_open_positions", minimum=0),
            max_position_notional=_get_optional_positive(cfg, "max_position_notional"),
            max_total_exposure=_get_optional_positive(cfg, "max_total_exposure"),
            max_asset_exposure=_get_optional_positive(cfg, "max_asset_exposure"),
            max_leverage=get_float(cfg, "max_leverage"),
            fee_rate=get_float(cfg, "fee_rate"),
            slippage_rate=get_float(cfg, "slippage_rate"),
        )

    def evaluate(
        self,
        signal: Signal,
        account: AccountRiskState,
        price: float | None = None,
        atr: float | None = None,
        constraints: TradingConstraints | None = None,
        symbol: str | None = None,
        config: Mapping[str, object] | None = None,
    ) -> RiskDecision:
        """Evaluate a signal against the account risk state and limits.

        Args:
            signal: Signal produced by the signal engine.
            account: Current portfolio risk snapshot.
            price: Entry price override; defaults to ``signal.price``.
            atr: Current ATR value; required when ``stop_method`` is ``"atr"``.
            constraints: Optional normalized venue constraints.
            symbol: Optional instrument symbol enabling the per-asset exposure
                cap; without it that cap is skipped rather than guessed.
            config: Optional per-call overrides of constructor defaults.

        Returns:
            An immutable :class:`RiskDecision`. Normal conditions that prevent
            trading produce rejected decisions, never exceptions.

        Raises:
            ValueError: On invalid inputs (non-finite price/ATR) or invalid
                configuration.
        """
        cfg: dict[str, object] = {**self._config, **dict(config or {})}
        params = self._resolve_params(cfg)
        entry = self._validate_price(price if price is not None else signal.price)
        shared: dict[str, object] = {
            "entry_price": entry,
            "signal_direction": signal.direction.value,
            "symbol": symbol,
        }
        if signal.direction is SignalDirection.NONE:
            return self._reject(RejectionReason.NO_SIGNAL, shared)
        expected_reason = (
            SignalReason.SUPPORT_EDGE_SETUP
            if signal.direction is SignalDirection.LONG
            else SignalReason.RESISTANCE_EDGE_SETUP
        )
        if signal.reason is not expected_reason:
            return self._reject(
                RejectionReason.INVALID_SIGNAL, {**shared, "signal_reason": signal.reason.value}
            )

        gate_rejection = self._run_account_gates(account, params, shared)
        if gate_rejection is not None:
            return gate_rejection

        stop = self._compute_stop(signal, entry, params, atr, shared)
        if isinstance(stop, RiskDecision):
            return stop
        stop_distance = abs(entry - stop)
        if not math.isfinite(stop_distance) or stop_distance <= 0.0:
            return self._reject(RejectionReason.INVALID_STOP, {**shared, "stop_price": stop})

        risk_amount = params.risk_per_trade * account.equity
        requested_quantity = risk_amount / stop_distance
        shaped = self._apply_caps(
            account, constraints, symbol, params, requested_quantity * entry
        )
        if isinstance(shaped, RiskDecision):
            return shaped
        capped_notional, cap_metadata = shaped

        target = self._compute_target(signal, entry, stop_distance, params)
        if isinstance(target, RiskDecision):
            return target
        target = self._round_tick(target, entry, constraints, toward_entry=True)
        stop = self._round_tick(stop, entry, constraints, toward_entry=False)
        final_distance = abs(entry - stop)
        if final_distance <= 0.0:
            return self._reject(RejectionReason.INVALID_STOP, {**shared, "stop_price": stop})

        shaped_quantity = self._shape_quantity(capped_notional / entry, constraints)
        if isinstance(shaped_quantity, RiskDecision):
            return shaped_quantity
        quantity, constraint_notes = shaped_quantity
        final_notional = quantity * entry
        if constraints is not None and constraints.min_notional is not None:
            if final_notional < constraints.min_notional:
                return self._reject(
                    RejectionReason.EXCHANGE_CONSTRAINT,
                    {
                        "note": "notional_below_min",
                        "notional": final_notional,
                        "min_notional": constraints.min_notional,
                    },
                )
        exit_win = quantity * target
        exit_loss = quantity * stop
        fees_estimate = params.fee_rate * (final_notional + exit_win)
        slippage_estimate = params.slippage_rate * (final_notional + exit_win)
        potential_reward = abs(exit_win - final_notional) - fees_estimate - slippage_estimate
        potential_loss = (
            quantity * final_distance
            + params.fee_rate * (final_notional + exit_loss)
            + params.slippage_rate * (final_notional + exit_loss)
        )
        reward_risk = potential_reward / potential_loss

        metadata: dict[str, object] = {
            **shared,
            **cap_metadata,
            "constraints_applied": constraint_notes,
            "stop_method": params.stop_method.value,
            "target_method": params.target_method.value,
            "fee_rate": params.fee_rate,
            "slippage_rate": params.slippage_rate,
            "requested_quantity": requested_quantity,
            "requested_notional": requested_quantity * entry,
            "equity": account.equity,
            "available_balance": account.available_balance,
            "allowed_leverage": self._allowed_leverage(params, constraints),
            "range_high": signal.range_high,
            "range_low": signal.range_low,
        }
        if reward_risk < params.min_reward_risk:
            return self._reject(
                RejectionReason.MIN_REWARD_RISK,
                {
                    **metadata,
                    "reward_risk_ratio": round(reward_risk, 6),
                    "required_reward_risk": params.min_reward_risk,
                    "stop_price": stop,
                    "target_price": target,
                    "position_quantity": quantity,
                },
            )
        used_leverage = (
            final_notional / account.available_balance if account.available_balance > 0 else 0.0
        )
        return RiskDecision(
            approved=True,
            status=RiskDecisionStatus.APPROVED,
            rejection_reason=None,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            risk_amount=risk_amount,
            requested_quantity=requested_quantity,
            position_quantity=quantity,
            position_notional=final_notional,
            leverage=round(min(used_leverage, self._allowed_leverage(params, constraints)), 4),
            potential_reward=potential_reward,
            potential_loss=potential_loss,
            reward_risk_ratio=round(reward_risk, 6),
            fees_estimate=fees_estimate,
            slippage_estimate=slippage_estimate,
            metadata=metadata,
        )

    @staticmethod
    def _validate_price(price: object) -> float:
        """Validate that an entry price is a finite positive number."""
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise ValueError(f"price must be a real number, got {type(price).__name__}")
        result = float(price)
        if not math.isfinite(result) or result <= 0.0:
            raise ValueError(f"price must be finite and positive, got {result}")
        return result

    @staticmethod
    def _allowed_leverage(params: RiskParams, constraints: TradingConstraints | None) -> float:
        """Effective leverage ceiling: engine config tightened by venue limits."""
        if constraints is not None and constraints.max_leverage is not None:
            return min(params.max_leverage, constraints.max_leverage)
        return params.max_leverage

    def _run_account_gates(
        self, account: AccountRiskState, params: RiskParams, shared: dict[str, object]
    ) -> RiskDecision | None:
        """Run pre-sizing protective gates; return a rejection or None."""
        if account.equity <= 0.0:
            return self._reject(RejectionReason.DRAWDOWN_LIMIT, {**shared, "gate": "zero_equity"})
        peak = max(account.peak_equity, account.equity)
        drawdown = (peak - account.equity) / peak if peak > 0.0 else 0.0
        if drawdown >= params.max_drawdown:
            return self._reject(
                RejectionReason.DRAWDOWN_LIMIT,
                {**shared, "drawdown": round(drawdown, 6), "limit": params.max_drawdown},
            )
        daily_dd = (
            (account.daily_start_equity - account.equity) / account.daily_start_equity
            if account.daily_start_equity > 0.0
            else 0.0
        )
        if daily_dd >= params.max_daily_drawdown:
            return self._reject(
            RejectionReason.DAILY_LOSS_LIMIT,
            {
                **shared,
                "daily_drawdown": round(daily_dd, 6),
                "limit": params.max_daily_drawdown,
            },
        )
        if account.consecutive_losses >= params.max_consecutive_losses:
            return self._reject(
                RejectionReason.CONSECUTIVE_LOSS_LIMIT,
                {
                    **shared,
                    "consecutive_losses": account.consecutive_losses,
                    "limit": params.max_consecutive_losses,
                },
            )
        if len(account.open_positions) >= params.max_open_positions:
            return self._reject(
                RejectionReason.MAX_OPEN_POSITIONS,
                {
                    **shared,
                    "open_positions": len(account.open_positions),
                    "limit": params.max_open_positions,
                },
            )
        return None

    def _compute_stop(
        self,
        signal: Signal,
        entry: float,
        params: RiskParams,
        atr: float | None,
        shared: dict[str, object],
    ) -> float | RiskDecision:
        """Compute the protective stop for the configured method."""
        is_long = signal.direction is SignalDirection.LONG
        if params.stop_method is StopMethod.RANGE:
            bounds = self._require_bounds(signal, shared)
            if isinstance(bounds, RiskDecision):
                return bounds
            low, high = bounds
            offset = params.range_stop_buffer * (high - low)
            return low - offset if is_long else high + offset
        if params.stop_method is StopMethod.ATR:
            if atr is None:
                raise ValueError("An 'atr' value is required when stop_method is 'atr'")
            if not math.isfinite(atr) or atr <= 0.0:
                raise ValueError(f"atr must be finite and positive, got {atr}")
            distance = params.atr_multiplier * atr
            return entry - distance if is_long else entry + distance
        distance = params.fixed_stop_percent * entry
        return entry - distance if is_long else entry + distance

    def _compute_target(
        self,
        signal: Signal,
        entry: float,
        stop_distance: float,
        params: RiskParams,
    ) -> float | RiskDecision:
        """Compute the profit target for the configured method."""
        is_long = signal.direction is SignalDirection.LONG
        if params.target_method is TargetMethod.OPPOSITE_RANGE_EDGE:
            bounds = self._require_bounds(signal, {})
            if isinstance(bounds, RiskDecision):
                return bounds
            low, high = bounds
            return high if is_long else low
        if params.target_method is TargetMethod.RANGE_FRACTION:
            bounds = self._require_bounds(signal, {})
            if isinstance(bounds, RiskDecision):
                return bounds
            low, high = bounds
            span = params.range_target_fraction * (high - low)
            return low + span if is_long else high - span
        offset = params.fixed_rr_ratio * stop_distance
        return entry + offset if is_long else entry - offset

    @staticmethod
    def _require_bounds(
        signal: Signal, shared: dict[str, object]
    ) -> tuple[float, float] | RiskDecision:
        """Extract finite range bounds or reject with INVALID_SIGNAL context."""
        high, low = signal.range_high, signal.range_low
        if high is None or low is None or math.isnan(high) or math.isnan(low):
            return RiskEngine._reject(
                RejectionReason.INVALID_SIGNAL,
                {**shared, "note": "method_requires_range_bounds"},
            )
        return low, high

    def _apply_caps(
        self,
        account: AccountRiskState,
        constraints: TradingConstraints | None,
        symbol: str | None,
        params: RiskParams,
        desired_notional: float,
    ) -> tuple[float, dict[str, object]] | RiskDecision:
        """Shape desired notional by soft caps, then validate funding.

        Soft limits (max position notional, portfolio/asset exposure rooms)
        shrink the position while staying tradable. Funding is binary: a
        desired notional beyond ``balance x allowed_leverage`` rejects with
        INSUFFICIENT_BALANCE or LEVERAGE_LIMIT rather than silently resizing.
        """
        allowed_leverage = self._allowed_leverage(params, constraints)
        affordable = account.available_balance * allowed_leverage
        capped = desired_notional
        binding: str | None = None
        soft_caps: list[tuple[str, float]] = []
        if params.max_position_notional is not None:
            soft_caps.append(("position_size", params.max_position_notional))
        if params.max_total_exposure is not None:
            exposure_room = params.max_total_exposure - account.total_exposure
            soft_caps.append(("portfolio_exposure", exposure_room))
        if params.max_asset_exposure is not None and symbol is not None:
            asset_exposure = sum(
                pos.notional for pos in account.open_positions if pos.symbol == symbol
            )
            soft_caps.append(("asset_exposure", params.max_asset_exposure - asset_exposure))
        for name, value in soft_caps:
            if value < capped:
                capped, binding = value, name
        metadata: dict[str, object] = {
            "binding_constraint": binding,
            "applied_caps": {
                name: value
                for name, value in {**dict(soft_caps), "balance_leverage": affordable}.items()
                if math.isfinite(value)
            },
            "desired_notional": desired_notional,
        }
        if capped <= 0.0:
            return self._reject(self._zero_room_reason(binding, affordable), metadata)
        if capped > affordable:
            reason = self._funding_rejection_reason(
                capped, account.available_balance, params, constraints
            )
            return self._reject(reason, {**metadata, "cap_value": affordable})
        return capped, metadata

    @staticmethod
    def _zero_room_reason(binding: str | None, affordable: float) -> RejectionReason:
        """Map a non-positive cap room to its rejection reason."""
        if affordable <= 0.0:
            return RejectionReason.INSUFFICIENT_BALANCE
        if binding == "position_size":
            return RejectionReason.MAX_POSITION_SIZE
        return RejectionReason.MAX_PORTFOLIO_EXPOSURE

    @staticmethod
    def _funding_rejection_reason(
        desired_notional: float,
        available_balance: float,
        params: RiskParams,
        constraints: TradingConstraints | None,
    ) -> RejectionReason:
        """Distinguish 'venue tightened leverage' from 'account cannot fund'."""
        if available_balance <= 0.0:
            return RejectionReason.INSUFFICIENT_BALANCE
        leverage_needed = desired_notional / available_balance
        allowed = RiskEngine._allowed_leverage(params, constraints)
        if leverage_needed > allowed and leverage_needed <= params.max_leverage:
            return RejectionReason.LEVERAGE_LIMIT
        return RejectionReason.INSUFFICIENT_BALANCE

    @staticmethod
    def _shape_quantity(
        quantity: float, constraints: TradingConstraints | None
    ) -> tuple[float, list[str]] | RiskDecision:
        """Clamp/floor quantity to venue constraints; never invents them.

        Returns the shaped quantity plus human-readable notes of applied
        shapings, or a rejection when the result violates a minimum.
        """
        if constraints is None:
            return quantity, []
        notes: list[str] = []
        if constraints.max_quantity is not None and quantity > constraints.max_quantity:
            quantity = constraints.max_quantity
            notes.append("max_quantity_clamp")
        if constraints.quantity_step is not None:
            stepped = (
                math.floor(quantity / constraints.quantity_step + 1e-12)
                * constraints.quantity_step
            )
            quantity = round(stepped, 12)
            notes.append("quantity_step_rounding")
        if constraints.min_quantity is not None and quantity < constraints.min_quantity:
            return RiskDecision(
                approved=False,
                status=RiskDecisionStatus.REJECTED,
                rejection_reason=RejectionReason.EXCHANGE_CONSTRAINT,
                metadata={"note": "quantity_below_min", "quantity": quantity},
            )
        return quantity, notes

    @staticmethod
    def _round_tick(
        value: float, entry: float, constraints: TradingConstraints | None, *, toward_entry: bool
    ) -> float:
        """Round a price to the venue tick.

        Stops round away from entry (preserving planned risk); targets round
        toward entry (conservatively reducing planned reward).
        """
        if constraints is None or constraints.price_tick is None:
            return value
        tick = constraints.price_tick
        above_entry = value > entry
        use_floor = (above_entry and not toward_entry) or (not above_entry and toward_entry)
        if use_floor:
            return math.floor(value / tick + 1e-9) * tick
        return math.ceil(value / tick - 1e-9) * tick

    @staticmethod
    def _reject(reason: RejectionReason, metadata: dict[str, object]) -> RiskDecision:
        """Build a rejected decision carrying full diagnostic context."""
        return RiskDecision(
            approved=False,
            status=RiskDecisionStatus.REJECTED,
            rejection_reason=reason,
            metadata=metadata,
        )
