"""Factory instantiating range detectors from declarative configuration."""

from collections.abc import Mapping

import pandas as pd

from range_engine.base import RangeDetector, RangeState
from range_engine.manual import ManualRangeDetector
from range_engine.oscillator import OscillatorConfirmedRangeDetector
from range_engine.structural import StructuralRangeDetector
from range_engine.volatility import VolatilityRangeDetector


class RangeEngineFactory:
    """Builds detectors from config dicts like ``{"mode": ..., "params": {...}}``.

    The mode defaults to ``structural`` when omitted. For
    ``oscillator_confirmed``, ``params["base"]`` may hold a nested detector
    config (same shape) which supplies the wrapped boundary detector.
    """

    OSCILLATOR_CONFIRMED_MODE: str = "oscillator_confirmed"

    _REGISTRY: dict[str, type[RangeDetector]] = {
        "manual": ManualRangeDetector,
        "volatility": VolatilityRangeDetector,
        "structural": StructuralRangeDetector,
    }

    @classmethod
    def available_modes(cls) -> tuple[str, ...]:
        """All selectable mode names, including the composite wrapper."""
        return (*cls._REGISTRY, cls.OSCILLATOR_CONFIRMED_MODE)

    @classmethod
    def create(cls, config: Mapping[str, object] | None = None) -> RangeDetector:
        """Instantiate the detector described by ``config``.

        Args:
            config: ``{"mode": str, "params": dict}``; both keys optional.

        Returns:
            A ready-to-use :class:`RangeDetector` instance.

        Raises:
            ValueError: If ``mode`` is unknown or has a non-string value.
        """
        cfg = dict(config or {})
        raw_mode = cfg.get("mode", "structural")
        if not isinstance(raw_mode, str):
            raise ValueError(f"Config key 'mode' must be a string, got {type(raw_mode).__name__}")
        if raw_mode in cls._REGISTRY:
            return cls._REGISTRY[raw_mode]()
        if raw_mode == cls.OSCILLATOR_CONFIRMED_MODE:
            params = cls._extract_params(cfg)
            raw_base = params.get("base")
            if isinstance(raw_base, Mapping):
                return OscillatorConfirmedRangeDetector(
                    base=cls.create(raw_base),
                    base_config=cls._flatten_config(dict(raw_base)),
                )
            return OscillatorConfirmedRangeDetector()
        allowed = ", ".join(repr(mode) for mode in cls.available_modes())
        raise ValueError(f"Unknown range detector mode {raw_mode!r}. Available modes: {allowed}")

    @classmethod
    def detect(cls, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """One-shot convenience: create the configured detector and run it.

        Keys from ``params`` are flattened into the effective per-call config;
        top-level keys other than ``mode``/``params`` override them.

        Args:
            df: OHLCV candle frame.
            config: Factory config as accepted by :meth:`create`.

        Returns:
            The resulting :class:`RangeState`.

        Raises:
            ValueError: On unknown modes or invalid parameters.
        """
        cfg = dict(config or {})
        detector = cls.create(cfg)
        effective = cls._flatten_config(cfg)
        return detector.detect(df, effective)

    @classmethod
    def _flatten_config(cls, config: Mapping[str, object]) -> dict[str, object]:
        """Merge ``params`` and top-level keys into one flat per-call config."""
        cfg = dict(config)
        flattened = dict(cls._extract_params(cfg))
        overrides = {key: value for key, value in cfg.items() if key not in ("mode", "params")}
        flattened.update(overrides)
        return flattened

    @staticmethod
    def _extract_params(cfg: Mapping[str, object]) -> dict[str, object]:
        """Pull the nested ``params`` mapping out of a factory config."""
        raw_params = cfg.get("params")
        if raw_params is None:
            return {}
        if not isinstance(raw_params, Mapping):
            raise ValueError(
                f"Config key 'params' must be a mapping, got {type(raw_params).__name__}"
            )
        return dict(raw_params)
