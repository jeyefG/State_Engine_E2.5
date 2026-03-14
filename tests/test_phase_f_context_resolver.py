# tests/test_phase_f_context_resolver.py

from state_engine.phase_f.context_resolver import ContextResolver
from state_engine.phase_f.types import ContextRow


def test_candidates_order_and_none_normalization():
    r = ContextRow(
        symbol="XAUUSD.mg",
        ts="2025-01-01T00:00:00",
        state="TREND",
        ql="TREND_STRONG",
        lf="LOOK_FOR_trend_strong_orderly",
    )
    res = ContextResolver(none_token="NONE")
    cands = res.candidates(r)

    assert cands[0] == "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly"
    assert cands[1] == "STATE=TREND|QL=NONE|LF=LOOK_FOR_trend_strong_orderly"
    assert cands[2] == "STATE=TREND|QL=TREND_STRONG|LF=NONE"
    assert cands[3] == "STATE=TREND|QL=NONE|LF=NONE"

    r2 = ContextRow(symbol="XAUUSD.mg", ts="t", state="BALANCE", ql="", lf=None)
    c2 = res.candidates(r2)
    assert c2[0] == "STATE=BALANCE|QL=NONE|LF=NONE"
