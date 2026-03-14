from __future__ import annotations
from typing import Dict, Any, Optional, Set
import yaml
from .types import ContextRow, PhaseEStats, PolicyDecision
from .context_resolver import ContextResolver

class PhaseERegistry:
    """
    Interfaz mínima: dado (symbol, context_key) retorna stats o None.
    Implementación concreta: cargar desde CSV/Parquet (no lo meto acá).
    """
    def get(self, symbol: str, context_key: str) -> Optional[PhaseEStats]:
        raise NotImplementedError


class PolicyEngine:
    """
    - Decide ALLOW/BLOCK basado en policy YAML + thresholds GO/NO-GO.
    - NO ejecuta trades.
    """

    def __init__(self, policy_path: str, registry: PhaseERegistry):
        self.policy = self._load_policy(policy_path)
        self.registry = registry

        self.symbol = self.policy["symbol"]
        self.go_thresholds = self.policy["go_thresholds"]
        self.limits = self.policy["limits"]
        self.templates = self.policy["templates"]
        self.risk_profiles = self.policy["risk_profiles"]

        # set de context_keys GO
        self.go_map: Dict[str, Dict[str, Any]] = {
            item["context_key"]: item for item in self.policy.get("go_contexts", [])
        }
        self.risk_off_map: Dict[str, Dict[str, Any]] = {
            item["context_key"]: item for item in self.policy.get("risk_off", [])
        }

        res_cfg = self.policy["context_resolution"]
        self.resolver = ContextResolver(
            none_token=res_cfg.get("none_token", "NONE"),
            priority=res_cfg.get("priority", None),
        )

    def _load_policy(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _passes_thresholds(self, s: PhaseEStats) -> bool:
        if s.n_bars < self.go_thresholds["min_n_bars"]:
            return False
        if s.uplift_pp < self.go_thresholds["min_uplift_pp"]:
            return False
        if s.wf_score < self.go_thresholds.get("min_wf_score", 0.0):
            return False
        return True

    def _resolution_level_from_ck(self, ck: str) -> str:
        """
        Clasifica el nivel de resolución del contexto *seleccionado*.
        OJO: Esto NO cambia el context_key, solo etiqueta auditoría.

        Convención:
          - STATE_QL_LF: QL!=NONE y LF!=NONE
          - STATE_LF:    QL=NONE y LF!=NONE
          - STATE_QL:    QL!=NONE y LF=NONE
          - STATE:       QL=NONE y LF=NONE
        """
        ck = str(ck or "").strip()
        # defaults conservadores
        ql = "NONE"
        lf = "NONE"
        try:
            parts = ck.split("|")
            for p in parts:
                if p.startswith("QL="):
                    ql = p.split("=", 1)[1].strip()
                elif p.startswith("LF="):
                    lf = p.split("=", 1)[1].strip()
        except Exception:
            pass

        none = self.resolver.none_token if hasattr(self.resolver, "none_token") else "NONE"
        ql_is_none = (ql == none)
        lf_is_none = (lf == none)

        if (not ql_is_none) and (not lf_is_none):
            return "STATE_QL_LF"
        if ql_is_none and (not lf_is_none):
            return "STATE_LF"
        if (not ql_is_none) and lf_is_none:
            return "STATE_QL"
        return "STATE"

    def _meta_resolution(self, candidates: list[str], chosen_ck: str) -> dict:
        """
        Meta común para auditoría:
          - candidate_rank (0 = mejor candidato)
          - context_resolution_level (STATE_QL_LF / STATE_LF / STATE_QL / STATE)
          - candidates_n (para sanity)
        """
        rank = None
        try:
            rank = candidates.index(chosen_ck)
        except Exception:
            # si por cualquier motivo no está, dejamos None
            rank = None

        return {
            "candidate_rank": rank,
            "context_resolution_level": self._resolution_level_from_ck(chosen_ck),
            "candidates_n": len(candidates) if candidates else 0,
        }
    def decide(self, r: ContextRow) -> PolicyDecision:
        if r.symbol != self.symbol:
            return PolicyDecision(
                decision="BLOCK",
                context_key="STATE=NONE|QL=NONE|LF=NONE",
                meta={
                    "reason": "symbol_mismatch",
                    "candidate_rank": None,
                    "context_resolution_level": "STATE",
                    "candidates_n": 0,
                },
            )
    
        candidates = self.resolver.candidates(r)
    
        # Risk-off: safety first. If expected_baseline_id provided, enforce it.
        for ck in candidates:
            if ck in self.risk_off_map:
                item = self.risk_off_map[ck]
                expected = item.get("expected_baseline_id")
    
                stats = self.registry.get(r.symbol, ck) if expected else None
                if expected and stats is not None and stats.baseline_id != expected:
                    continue
    
                meta = {"reason": "risk_off", **item}
                if stats is not None:
                    meta.update({
                        "baseline_id": stats.baseline_id,
                        "uplift_pp": stats.uplift_pp,
                        "n_bars": stats.n_bars,
                        "wf_score": stats.wf_score,
                    })
                meta.update(self._meta_resolution(candidates, ck))
                return PolicyDecision(decision="BLOCK", context_key=ck, meta=meta)
    
        # GO selection: first candidate in GO map that passes Phase E thresholds + baseline guardrail
        for ck in candidates:
            if ck not in self.go_map:
                continue
    
            stats = self.registry.get(r.symbol, ck)
            if stats is None:
                continue
            if not self._passes_thresholds(stats):
                continue
    
            item = self.go_map[ck]
            expected = item.get("expected_baseline_id")
            if expected and stats.baseline_id != expected:
                continue
            
            meta = {
                "baseline_id": stats.baseline_id,
                "uplift_pp": stats.uplift_pp,
                "n_bars": stats.n_bars,
                "wf_score": stats.wf_score,
            }
            meta.update(self._meta_resolution(candidates, ck))
    
            return PolicyDecision(
                decision="ALLOW",
                context_key=ck,
                trade_template=item["trade_template"],
                risk_profile=item["risk_profile"],
                direction_policy=item["direction_policy"],
                meta=meta
            )
    
        # NO-GO fallback:
        # We keep a candidate context_key for diagnostics, but we also export:
        # - meta_candidate_rank
        # - meta_context_resolution_level
        # so audits can distinguish "QL missing" vs "QL present but not selected by priority".
        
        chosen = candidates[-1] if candidates else "NONE"
        meta = {"reason": "no_go_context"}
        meta.update(self._meta_resolution(candidates, chosen))
        return PolicyDecision(
            decision="BLOCK",
            context_key=chosen, 
            meta=meta,
        )