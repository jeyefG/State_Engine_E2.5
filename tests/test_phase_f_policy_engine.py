# tests/test_phase_f_policy_engine.py

from pathlib import Path
import yaml

from state_engine.phase_f.policy_engine import PolicyEngine
from state_engine.phase_f.registry import PhaseECSVRegistry
from state_engine.phase_f.types import ContextRow


def write_csv(path: Path, header, rows):
    import csv
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_policy_engine_allows_go_context(tmp_path: Path):
    # Registry CSV
    p = tmp_path / "phasee.csv"
    header = ["base_state", "quality_label_full", "look_for_rule", "baseline_id", "uplift_pp", "n_bars"]
    rows = [
        ["TREND", "TREND_STRONG", "LOOK_FOR_trend_strong_orderly", "STATE_REINFORCEMENT", "10.8", "1160"],
    ]
    write_csv(p, header, rows)
    reg = PhaseECSVRegistry(symbol="XAUUSD.mg", csv_paths=[p], none_token="NONE")

    # Policy YAML
    policy = {
        "version": 1,
        "symbol": "XAUUSD.mg",
        "limits": {"max_positions": 1, "max_trades_per_day": 6, "daily_stop_R": -1.5, "allow_overlapping_trades": False},
        "go_thresholds": {"min_n_bars": 300, "min_uplift_pp": 6.0, "min_wf_score": 0.0},
        "context_resolution": {"priority": ["STATE_QL_LF", "STATE_LF", "STATE_QL", "STATE"], "none_token": "NONE"},
        "risk_profiles": {"RP_TCP": {"risk_per_trade": 0.005, "cooldown_bars": 4, "time_stop_bars": 16, "trailing": True}},
        "templates": {"TCP": {"entry": {"trigger_type": "PULLBACK_SIMPLE", "trigger_window_bars": 6}, "exits": {"invalidate_on_context_block": True}}},
        "go_contexts": [
            {
                "context_key": "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly",
                "trade_template": "TCP",
                "risk_profile": "RP_TCP",
                "direction_policy": "WITH_TREND",
            }
        ],
        "risk_off": [],
    }
    y = tmp_path / "policy.yaml"
    y.write_text(yaml.safe_dump(policy), encoding="utf-8")

    pe = PolicyEngine(policy_path=str(y), registry=reg)

    r = ContextRow(
        symbol="XAUUSD.mg",
        ts="t",
        state="TREND",
        ql="TREND_STRONG",
        lf="LOOK_FOR_trend_strong_orderly",
        atr=1.0,
    )
    dec = pe.decide(r)
    assert dec.decision == "ALLOW"
    assert dec.trade_template == "TCP"
    assert dec.risk_profile == "RP_TCP"


def test_policy_engine_blocks_when_thresholds_fail(tmp_path: Path):
    # Registry CSV with too low n_bars
    p = tmp_path / "phasee.csv"
    header = ["base_state", "quality_label_full", "look_for_rule", "baseline_id", "uplift_pp", "n_bars"]
    rows = [
        ["TREND", "TREND_STRONG", "LOOK_FOR_trend_strong_orderly", "STATE_REINFORCEMENT", "10.8", "10"],
    ]
    write_csv(p, header, rows)
    reg = PhaseECSVRegistry(symbol="XAUUSD.mg", csv_paths=[p], none_token="NONE")

    policy = {
        "version": 1,
        "symbol": "XAUUSD.mg",
        "limits": {"max_positions": 1, "max_trades_per_day": 6, "daily_stop_R": -1.5, "allow_overlapping_trades": False},
        "go_thresholds": {"min_n_bars": 300, "min_uplift_pp": 6.0, "min_wf_score": 0.0},
        "context_resolution": {"priority": ["STATE_QL_LF", "STATE_LF", "STATE_QL", "STATE"], "none_token": "NONE"},
        "risk_profiles": {"RP_TCP": {"risk_per_trade": 0.005, "cooldown_bars": 4, "time_stop_bars": 16, "trailing": True}},
        "templates": {"TCP": {"entry": {"trigger_type": "PULLBACK_SIMPLE", "trigger_window_bars": 6}, "exits": {"invalidate_on_context_block": True}}},
        "go_contexts": [
            {
                "context_key": "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly",
                "trade_template": "TCP",
                "risk_profile": "RP_TCP",
                "direction_policy": "WITH_TREND",
            }
        ],
    }
    y = tmp_path / "policy.yaml"
    y.write_text(yaml.safe_dump(policy), encoding="utf-8")

    pe = PolicyEngine(policy_path=str(y), registry=reg)

    r = ContextRow(symbol="XAUUSD.mg", ts="t", state="TREND", ql="TREND_STRONG", lf="LOOK_FOR_trend_strong_orderly")
    dec = pe.decide(r)
    assert dec.decision == "BLOCK"
