from dataclasses import replace

from state_engine.phase_f.template_executor import TemplateExecutor, Broker, Position
from state_engine.phase_f.types import ContextRow, PolicyDecision


class FakeBroker(Broker):
    def __init__(self, price: float = 100.0):
        self._price = price
        self._pos = None
        self.last_close_reason = None
        self.open_calls = 0
        self.close_calls = 0

    def has_open_position(self, symbol: str) -> bool:
        return self._pos is not None and self._pos.symbol == symbol

    def get_open_position(self, symbol: str):
        if self._pos is None:
            return None
        return self._pos if self._pos.symbol == symbol else None

    def open_market(self, symbol: str, side: str, size: float, stop_price: float, meta: dict) -> None:
        self.open_calls += 1
        self._pos = Position(
            symbol=symbol,
            side=side,
            entry_ts="t0",
            entry_price=self._price,
            stop_price=stop_price,
            size=size,
            meta=meta,
        )

    def close_position(self, symbol: str, reason: str) -> None:
        if self._pos and self._pos.symbol == symbol:
            self.close_calls += 1
            self.last_close_reason = reason
            self._pos = None

    def get_price(self, symbol: str) -> float:
        return self._price


class TestExecutor(TemplateExecutor):
    # fuerza entradas sin meter heurística real
    def _select_direction(self, direction_policy: str, r: ContextRow):
        # valida que nos llega un string (bug fix)
        assert isinstance(direction_policy, str)
        return "LONG"

    def _entry_trigger_ok(self, template_name: str, r: ContextRow, tpl_cfg: dict) -> bool:
        return True


def base_policy(invalidate_on_block: bool = True):
    return {
        "templates": {
            "TCP": {
                "entry": {"trigger_type": "X", "trigger_window_bars": 1},
                "exits": {"invalidate_on_context_block": invalidate_on_block},
            }
        },
        "risk_profiles": {
            "RP_TCP": {"risk_per_trade": 0.005, "cooldown_bars": 4, "time_stop_bars": 2, "trailing": False}
        },
        "limits": {"max_positions": 1},
    }


def base_decision_allow():
    return PolicyDecision(
        decision="ALLOW",
        context_key="STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly",
        trade_template="TCP",
        risk_profile="RP_TCP",
        direction_policy="WITH_TREND",
        meta={},
    )


def base_row(atr=1.0):
    return ContextRow(
        symbol="XAUUSD.mg",
        ts="t",
        state="TREND",
        ql="TREND_STRONG",
        lf="LOOK_FOR_trend_strong_orderly",
        atr=atr,
    )


def test_entry_requires_atr():
    broker = FakeBroker(price=100.0)
    exe = TestExecutor(policy=base_policy(), broker=broker)

    r = base_row(atr=None)
    dec = base_decision_allow()
    exe.on_bar(r, dec)

    assert broker.open_calls == 0
    assert not broker.has_open_position("XAUUSD.mg")


def test_close_on_block_respects_invalidate_flag_true():
    broker = FakeBroker(price=100.0)
    exe = TestExecutor(policy=base_policy(invalidate_on_block=True), broker=broker)

    # open
    exe.on_bar(base_row(atr=1.0), base_decision_allow())
    assert broker.has_open_position("XAUUSD.mg")

    # then context BLOCK -> should close
    dec_block = PolicyDecision(decision="BLOCK", context_key="STATE=TREND|QL=NONE|LF=NONE", meta={"reason": "no_go"})
    exe.on_bar(base_row(atr=1.0), dec_block)

    assert not broker.has_open_position("XAUUSD.mg")
    assert broker.last_close_reason == "context_block"
    # cooldown set by risk profile, not hardcoded 3
    assert exe._cooldown.get("XAUUSD.mg") == 4


def test_close_on_block_respects_invalidate_flag_false():
    broker = FakeBroker(price=100.0)
    exe = TestExecutor(policy=base_policy(invalidate_on_block=False), broker=broker)

    # open
    exe.on_bar(base_row(atr=1.0), base_decision_allow())
    assert broker.has_open_position("XAUUSD.mg")

    # then context BLOCK -> should NOT close
    dec_block = PolicyDecision(decision="BLOCK", context_key="STATE=TREND|QL=NONE|LF=NONE", meta={"reason": "no_go"})
    exe.on_bar(base_row(atr=1.0), dec_block)

    assert broker.has_open_position("XAUUSD.mg")
    assert broker.close_calls == 0


def test_time_stop_closes_and_sets_cooldown_from_profile():
    broker = FakeBroker(price=100.0)
    exe = TestExecutor(policy=base_policy(invalidate_on_block=True), broker=broker)

    # open
    exe.on_bar(base_row(atr=1.0), base_decision_allow())
    assert broker.has_open_position("XAUUSD.mg")

    # keep ALLOW so it doesn't context-close; time_stop_bars=2
    dec_allow = base_decision_allow()
    exe.on_bar(base_row(atr=1.0), dec_allow)  # bars_in_trade -> 1
    assert broker.has_open_position("XAUUSD.mg")

    exe.on_bar(base_row(atr=1.0), dec_allow)  # bars_in_trade -> 2 => close
    assert not broker.has_open_position("XAUUSD.mg")
    assert broker.last_close_reason == "time_stop"
    assert exe._cooldown.get("XAUUSD.mg") == 4
