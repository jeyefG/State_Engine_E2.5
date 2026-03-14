from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from .types import ContextRow, PolicyDecision


@dataclass
class Position:
    symbol: str
    side: str           # "LONG" or "SHORT"
    entry_ts: Any
    entry_price: float
    stop_price: float
    size: float
    bars_in_trade: int = 0
    meta: Optional[Dict[str, Any]] = None


class Broker:
    """
    Interfaz mínima para que TemplateExecutor sea agnóstico (backtest o MT5).
    """
    def has_open_position(self, symbol: str) -> bool:
        raise NotImplementedError

    def get_open_position(self, symbol: str) -> Optional[Position]:
        raise NotImplementedError

    def open_market(self, symbol: str, side: str, size: float, stop_price: float, meta: Dict[str, Any]) -> None:
        raise NotImplementedError

    def close_position(self, symbol: str, reason: str) -> None:
        raise NotImplementedError

    def get_price(self, symbol: str) -> float:
        raise NotImplementedError


class TemplateExecutor:
    """
    - Usa PolicyDecision (ALLOW/BLOCK) + template params para ejecutar.
    - NO decide qué contexto es bueno: eso ya lo decidió PolicyEngine.
    """

    def __init__(self, policy: dict, broker: Broker):
        self.policy = policy
        self.broker = broker
        self.templates = policy["templates"]
        self.risk_profiles = policy["risk_profiles"]
        self.limits = policy.get("limits", {})
        self._cooldown: Dict[str, int] = {}  # symbol -> bars remaining

    def on_bar(self, r: ContextRow, dec: PolicyDecision) -> None:
        sym = r.symbol

        # cooldown decrement
        if sym in self._cooldown and self._cooldown[sym] > 0:
            self._cooldown[sym] -= 1

        # Manage existing position
        if self.broker.has_open_position(sym):
            self._manage_open(r, dec)
            return

        # No position: consider entry
        if dec.decision != "ALLOW":
            return
        if self._cooldown.get(sym, 0) > 0:
            return

        # ATR is required if we might open (stop computation)
        if r.atr is None:
            return

        rp = self.risk_profiles[dec.risk_profile]
        tpl = self.templates[dec.trade_template]

        # FIX: pass direction_policy string (not the whole decision)
        side = self._select_direction(dec.direction_policy, r)
        if side is None:
            return

        if not self._entry_trigger_ok(dec.trade_template, r, tpl):
            return

        price = self.broker.get_price(sym)
        stop_price = self._compute_stop(dec.trade_template, r, price, side)

        size = self._compute_size(
            risk_per_trade=rp["risk_per_trade"],
            price=price,
            stop_price=stop_price
        )

        # Store template + risk_profile in position meta for consistent management later
        meta = {
            "context_key": dec.context_key,
            "trade_template": dec.trade_template,
            "risk_profile": dec.risk_profile,
            **(dec.meta or {}),
        }
        self.broker.open_market(sym, side=side, size=size, stop_price=stop_price, meta=meta)

    def _manage_open(self, r: ContextRow, dec: PolicyDecision) -> None:
        sym = r.symbol
        pos = self.broker.get_open_position(sym)
        if pos is None:
            return

        pos_meta = pos.meta or {}
        template_name = pos_meta.get("trade_template")
        risk_profile_name = pos_meta.get("risk_profile")

        # Resolve template + risk_profile from meta (preferred), else from current decision if ALLOW
        if template_name is None and dec.decision == "ALLOW":
            template_name = dec.trade_template
        if risk_profile_name is None and dec.decision == "ALLOW":
            risk_profile_name = dec.risk_profile

        # Default behavior (risk-first) if unknown
        invalidate_on_block = True
        if template_name and template_name in self.templates:
            invalidate_on_block = bool(
                self.templates[template_name]
                .get("exits", {})
                .get("invalidate_on_context_block", True)
            )

        cooldown_bars = 0
        if risk_profile_name and risk_profile_name in self.risk_profiles:
            cooldown_bars = int(self.risk_profiles[risk_profile_name].get("cooldown_bars", 0))

        time_stop_bars = None
        if risk_profile_name and risk_profile_name in self.risk_profiles:
            time_stop_bars = int(self.risk_profiles[risk_profile_name].get("time_stop_bars", 0))

        trailing_enabled = False
        if risk_profile_name and risk_profile_name in self.risk_profiles:
            trailing_enabled = bool(self.risk_profiles[risk_profile_name].get("trailing", False))

        # Invalidation: close on context BLOCK only if template says so
        if dec.decision != "ALLOW":
            if invalidate_on_block:
                self.broker.close_position(sym, reason="context_block")
                if cooldown_bars > 0:
                    self._cooldown[sym] = cooldown_bars
            return

        # Time-stop
        pos.bars_in_trade += 1
        if time_stop_bars and pos.bars_in_trade >= time_stop_bars:
            self.broker.close_position(sym, reason="time_stop")
            if cooldown_bars > 0:
                self._cooldown[sym] = cooldown_bars
            return

        # Trailing (placeholder; keep as no-op for now, no heuristics)
        if trailing_enabled:
            pass

    def _select_direction(self, direction_policy: str, r: ContextRow) -> Optional[str]:
        # Sin heurística extra: sólo políticas simples.
        # Requiere que el feed entregue dirección (p.ej. r.meta o state direccional) -> por ahora placeholder.
        if direction_policy == "BOTH":
            return None
        if direction_policy == "WITH_TREND":
            return None
        return None

    def _entry_trigger_ok(self, template_name: str, r: ContextRow, tpl_cfg: dict) -> bool:
        # Trigger mecánico mínimo: placeholder (sin gatillos todavía).
        return False

    def _compute_stop(self, template_name: str, r: ContextRow, price: float, side: str) -> float:
        # Stop por ATR como normalización. No es edge.
        if r.atr is None:
            raise ValueError("ATR missing for stop computation")
        k = 1.5
        return price - k * r.atr if side == "LONG" else price + k * r.atr

    def _compute_size(self, risk_per_trade: float, price: float, stop_price: float) -> float:
        # Placeholder: sizing real depende de equity y valor por punto del broker.
        return 0.01

