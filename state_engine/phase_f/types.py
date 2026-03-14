from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass(frozen=True)
class ContextRow:
    symbol: str
    ts: Any                      # datetime
    state: str                   # BALANCE/TRANSITION/TREND
    ql: str                      # e.g., TREND_STRONG or NONE
    lf: str                      # e.g., LOOK_FOR_* or NONE
    # minimal execution/risk normalization inputs (not edge)
    atr: Optional[float] = None
    spread: Optional[float] = None
    session: Optional[str] = None

@dataclass(frozen=True)
class PhaseEStats:
    context_key: str
    baseline_id: str
    uplift_pp: float
    n_bars: int
    wf_score: float = 0.0

@dataclass(frozen=True)
class PolicyDecision:
    decision: str                # "ALLOW" | "BLOCK"
    context_key: str
    trade_template: Optional[str] = None
    risk_profile: Optional[str] = None
    direction_policy: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
