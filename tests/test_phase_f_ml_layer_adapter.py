from pathlib import Path
import subprocess
import sys

import pandas as pd


def test_phase_f_ml_layer_adapter_contract(tmp_path: Path):
    ml_path = tmp_path / "preds.parquet"
    dec_path = tmp_path / "decisions.csv"
    out_path = tmp_path / "decisions_with_side_ml.csv"

    pd.DataFrame(
        {
            "timestamp": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
            "symbol": ["XAUUSD.mg", "XAUUSD.mg", "XAUUSD.mg"],
            "pred": [1, 2, 0],
            "pred_label": ["LONG", "SHORT", "NO_TRADE"],
            "proba_NO_TRADE": [0.1, 0.2, 0.8],
            "proba_LONG": [0.8, 0.1, 0.1],
            "proba_SHORT": [0.1, 0.7, 0.1],
        }
    ).to_parquet(ml_path, index=False)

    pd.DataFrame(
        {
            "symbol": ["XAUUSD.mg", "XAUUSD.mg", "XAUUSD.mg"],
            "ts": ["2025-01-01 00:00:00", "2025-01-01 01:00:00", "2025-01-01 02:00:00"],
            "context_key": ["A", "B", "C"],
            "baseline_id": ["BASE_A", "BASE_B", "BASE_C"],
        }
    ).to_csv(dec_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "scripts/phase_f_ml_layer_adapter.py",
            "--symbol",
            "XAUUSD.mg",
            "--ml_predictions",
            str(ml_path),
            "--phase_f_decisions_csv",
            str(dec_path),
            "--out_csv",
            str(out_path),
        ],
        check=True,
    )

    out = pd.read_csv(out_path)
    assert {"symbol", "ts", "decision", "setup_family", "side_intent"}.issubset(out.columns)

    assert out.loc[0, "decision"] == "ALLOW"
    assert out.loc[0, "side_intent"] == "LONG"
    assert out.loc[1, "side_intent"] == "SHORT"

    assert out.loc[2, "decision"] == "BLOCK"
    assert out.loc[2, "side_intent"] == "NONE"

    # merged context
    assert out.loc[0, "context_key"] == "A"
    assert out.loc[0, "meta_baseline_id"] == "BASE_A"
