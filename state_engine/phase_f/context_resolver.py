from __future__ import annotations
from typing import List
from .types import ContextRow

class ContextResolver:
    """
    Construye el context_key canónico y aplica jerarquía.
    NO mira PnL, NO decide trades. Sólo resuelve la llave.
    """

    def __init__(self, none_token: str = "NONE", priority: List[str] | None = None):
        self.none_token = none_token
        self.priority = priority or ["STATE_QL_LF", "STATE_LF", "STATE_QL", "STATE"]

    def _key_state_ql_lf(self, r: ContextRow) -> str:
        return f"STATE={r.state}|QL={r.ql}|LF={r.lf}"

    def _key_state_lf(self, r: ContextRow) -> str:
        return f"STATE={r.state}|QL={self.none_token}|LF={r.lf}"

    def _key_state_ql(self, r: ContextRow) -> str:
        return f"STATE={r.state}|QL={r.ql}|LF={self.none_token}"

    def _key_state(self, r: ContextRow) -> str:
        return f"STATE={r.state}|QL={self.none_token}|LF={self.none_token}"

    def candidates(self, r: ContextRow) -> List[str]:
        # Si QL/LF vienen vacíos, normaliza a NONE
        ql = r.ql or self.none_token
        lf = r.lf or self.none_token
        r = ContextRow(symbol=r.symbol, ts=r.ts, state=r.state, ql=ql, lf=lf,
                       atr=r.atr, spread=r.spread, session=r.session)
        keys = []
        for lvl in self.priority:
            if lvl == "STATE_QL_LF":
                keys.append(self._key_state_ql_lf(r))
            elif lvl == "STATE_LF":
                keys.append(self._key_state_lf(r))
            elif lvl == "STATE_QL":
                keys.append(self._key_state_ql(r))
            elif lvl == "STATE":
                keys.append(self._key_state(r))
        return keys
