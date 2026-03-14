# tests/test_phase_f_registry.py

from pathlib import Path

from state_engine.phase_f.registry import PhaseECSVRegistry, build_context_key


def write_csv(path: Path, header, rows):
    import csv
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def test_registry_builds_context_keys_and_get(tmp_path: Path):
    p = tmp_path / "phasee.csv"
    header = ["base_state", "quality_label_full", "look_for_rule", "baseline_id", "uplift_pp", "n_bars"]
    rows = [
        ["TREND", "TREND_STRONG", "LOOK_FOR_trend_strong_orderly", "STATE_REINFORCEMENT", "10.8", "1160"],
    ]
    write_csv(p, header, rows)

    reg = PhaseECSVRegistry(symbol="XAUUSD.mg", csv_paths=[p], none_token="NONE")

    ck = "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly"
    s = reg.get("XAUUSD.mg", ck)
    assert s is not None
    assert s.baseline_id == "STATE_REINFORCEMENT"
    assert abs(s.uplift_pp - 10.8) < 1e-9
    assert s.n_bars == 1160

    assert reg.get("EURUSD.mg", ck) is None


def test_registry_duplicate_resolution_by_max_n_bars(tmp_path: Path):
    p = tmp_path / "dup.csv"
    header = ["base_state", "quality_label_full", "look_for_rule", "baseline_id", "uplift_pp", "n_bars"]
    rows = [
        ["TREND", "TREND_STRONG", "LOOK_FOR_trend_strong_orderly", "A", "9.0", "100"],
        ["TREND", "TREND_STRONG", "LOOK_FOR_trend_strong_orderly", "B", "10.0", "200"],  # should win
    ]
    write_csv(p, header, rows)

    reg = PhaseECSVRegistry(symbol="XAUUSD.mg", csv_paths=[p], none_token="NONE")
    ck = "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly"
    s = reg.get("XAUUSD.mg", ck)
    assert s is not None
    assert s.baseline_id == "B"
    assert s.n_bars == 200


def test_registry_coverage(tmp_path: Path):
    p = tmp_path / "phasee.csv"
    header = ["base_state", "quality_label_full", "look_for_rule", "baseline_id", "uplift_pp", "n_bars"]
    rows = [
        ["BALANCE", "NONE", "LOOK_FOR_balance_compression", "BALANCE_STABILITY", "12.0", "370"],
    ]
    write_csv(p, header, rows)

    reg = PhaseECSVRegistry(symbol="XAUUSD.mg", csv_paths=[p], none_token="NONE")

    go = [
        "STATE=BALANCE|QL=NONE|LF=LOOK_FOR_balance_compression",
        "STATE=TREND|QL=TREND_STRONG|LF=LOOK_FOR_trend_strong_orderly",
    ]
    cov = reg.coverage(go)
    assert cov["total_go"] == 2
    assert cov["resolved_go"] == 1
    assert cov["missing_go"] == 1
    assert len(cov["missing_keys"]) == 1
