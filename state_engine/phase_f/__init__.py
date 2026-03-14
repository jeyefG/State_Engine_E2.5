# state_engine/__init__.py
"""
State_Engine_E package.

IMPORTANT:
- Keep this __init__ *minimal* to avoid import-time dependency failures
  (e.g., numpy/pandas/lightgbm) when users only need lightweight modules
  such as state_engine.phase_f.
- Heavy submodules should be imported lazily via __getattr__.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "__version__",
]

__version__ = "0.0.0"


# Optional: expose commonly-used modules lazily without import-time cost.
# Add entries only if you really need backward compatibility for old code.
_LAZY_ATTRS = {
    # "backtest": "state_engine.backtest",
    # "features": "state_engine.features",
    # "phase_a": "state_engine.phase_a",
    # "phase_b": "state_engine.phase_b",
    # "phase_c": "state_engine.phase_c",
    # "phase_d": "state_engine.phase_d",
    # "phase_e": "state_engine.phase_e",
    # Keep phase_f accessible but it is a package anyway.
    # "phase_f": "state_engine.phase_f",
}


def __getattr__(name: str) -> Any:
    """
    Lazy import to avoid hard dependency on heavy packages at import-time.
    """
    target = _LAZY_ATTRS.get(name)
    if not target:
        raise AttributeError(f"module 'state_engine' has no attribute '{name}'")

    mod = import_module(target)
    return mod


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_ATTRS.keys()))
