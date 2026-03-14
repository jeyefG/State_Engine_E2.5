# state_engine/phase_f/registry.py

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .types import PhaseEStats


def _norm_token(x: object, none_token: str = "NONE") -> str:
    """
    Normaliza tokens tipo STATE/QL/LF:
    - None, "", "nan", "none", "null" -> NONE
    - strings -> strip()
    """
    if x is None:
        return none_token
    s = str(x).strip()
    if s == "":
        return none_token
    s_low = s.lower()
    if s_low in {"nan", "none", "null"}:
        return none_token
    return s


def build_context_key(state: object, ql: object, lf: object, none_token: str = "NONE") -> str:
    s = _norm_token(state, none_token=none_token)
    q = _norm_token(ql, none_token=none_token)
    l = _norm_token(lf, none_token=none_token)
    return f"STATE={s}|QL={q}|LF={l}"


class PhaseECSVRegistry:
    """
    Loader concreto de Phase E desde CSVs (lookfor_state_filtered, lookfor_state_ql_filtered, etc.)
    Expone: get(symbol, context_key) -> PhaseEStats | None

    Columnas aceptadas:
      - base_state o state     (para STATE)
      - quality_label_full / quality_label / ql (para QL; opcional)
      - look_for_rule / lf     (para LF; opcional)
      - baseline_id            (requerida)
      - uplift_pp              (requerida)
      - n_bars                 (requerida)
      - wf_score               (opcional; default 0.0)

    Regla de duplicados:
      - si 2 filas mapean al mismo context_key, gana la de mayor n_bars
    """

    REQUIRED = {"baseline_id", "uplift_pp", "n_bars"}

    def __init__(self, symbol: str, csv_paths: List[str | Path], none_token: str = "NONE"):
        self.symbol = symbol
        self.none_token = none_token
        self._stats: Dict[str, PhaseEStats] = {}
        self._sources: Dict[str, Tuple[str, int]] = {}  # context_key -> (file, row_idx)
        self._load_all(csv_paths)

    def _load_all(self, csv_paths: Iterable[str | Path]) -> None:
        paths = [Path(p) for p in csv_paths]
        for p in paths:
            if not p.exists():
                raise FileNotFoundError(f"PhaseECSVRegistry: CSV not found: {p}")
            self._load_one(p)

    def _load_one(self, path: Path) -> None:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"PhaseECSVRegistry: empty header in {path}")

            cols = set(reader.fieldnames)
            missing = sorted(self.REQUIRED - cols)
            if missing:
                raise ValueError(
                    f"PhaseECSVRegistry: missing required columns {missing} in {path}. "
                    f"Found columns={sorted(cols)}"
                )

            # column candidates
            state_col = "base_state" if "base_state" in cols else ("state" if "state" in cols else None)
            if state_col is None:
                raise ValueError(
                    f"PhaseECSVRegistry: need 'base_state' or 'state' column in {path}. Found={sorted(cols)}"
                )

            # QL may be absent in state-level exports
            ql_col = None
            for c in ("quality_label_full", "quality_label", "ql"):
                if c in cols:
                    ql_col = c
                    break

            # LF may be absent in baseline exports
            lf_col = None
            for c in ("look_for_rule", "lf"):
                if c in cols:
                    lf_col = c
                    break

            wf_col = "wf_score" if "wf_score" in cols else None

            for i, row in enumerate(reader, start=1):
                state = row.get(state_col)
                ql = row.get(ql_col) if ql_col else self.none_token
                lf = row.get(lf_col) if lf_col else self.none_token
                ck = build_context_key(state, ql, lf, none_token=self.none_token)

                baseline_id = row["baseline_id"]
                uplift_pp = float(row["uplift_pp"])
                n_bars = int(float(row["n_bars"]))  # robust to "123.0"
                wf_score = float(row[wf_col]) if wf_col and row.get(wf_col, "") not in (None, "") else 0.0

                cand = PhaseEStats(
                    context_key=ck,
                    baseline_id=baseline_id,
                    uplift_pp=uplift_pp,
                    n_bars=n_bars,
                    wf_score=wf_score,
                )

                if ck in self._stats:
                    # keep the one with bigger n_bars
                    if cand.n_bars > self._stats[ck].n_bars:
                        self._stats[ck] = cand
                        self._sources[ck] = (str(path), i)
                else:
                    self._stats[ck] = cand
                    self._sources[ck] = (str(path), i)

    def get(self, symbol: str, context_key: str) -> Optional[PhaseEStats]:
        if symbol != self.symbol:
            return None
        return self._stats.get(context_key)

    def coverage(self, go_keys: List[str]) -> dict:
        total = len(go_keys)
        resolved = sum(1 for k in go_keys if k in self._stats)
        missing_keys = [k for k in go_keys if k not in self._stats]
        pct = (resolved / total * 100.0) if total > 0 else 0.0
        return {
            "symbol": self.symbol,
            "total_go": total,
            "resolved_go": resolved,
            "missing_go": total - resolved,
            "resolved_pct": pct,
            "missing_keys": missing_keys,
        }

    def debug_sources(self, context_key: str) -> Optional[dict]:
        """
        Útil para auditoría: de qué archivo/fila salió un context_key.
        """
        if context_key not in self._sources:
            return None
        src, row_idx = self._sources[context_key]
        s = self._stats[context_key]
        return {"context_key": context_key, "source_file": src, "source_row": row_idx, "stats": asdict(s)}
