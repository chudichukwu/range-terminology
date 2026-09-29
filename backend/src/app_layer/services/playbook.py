"""Versioned starting settings; existing saved strategies are never rewritten."""

from copy import deepcopy

PRESET = {
    "range_config": {
        "mode": "balanced",
        "lookback": 100,
        "pivot_window": 2,
        "min_touches": 2,
        "touch_tolerance": 0.05,
        "min_height_atr": 2.5,
        "adx_max": 22.0,
        "adx_trend": 25.0,
        "ema_slope_atr": 0.15,
    },
    "signal_config": {
        "entry_mode": "confirmed",
        "edge_zone": 0.15,
        "reclaim_bars": 3,
        "confirmation": "sfp_or_rejection",
        "volume_multiple": 0.0,
    },
    "risk_config": {
        "stop_buffer_atr": 0.375,
        "breakout_buffer_atr": 0.375,
        "hold_closes": 2,
        "tp1_fraction": 0.5,
        "target_inset": 0.02,
        "min_reward_risk": 2.0,
        "risk_per_trade": 0.01,
        "max_leverage": 3.0,
        "runner_fraction": 0.0,
    },
}


def range_touch_preset():
    """Legacy route name retained; returns the current balanced-range preset."""
    return deepcopy(PRESET)
