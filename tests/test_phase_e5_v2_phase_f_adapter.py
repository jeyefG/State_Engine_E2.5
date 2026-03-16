from pathlib import Path
import subprocess
import sys

import pandas as pd


def test_phase_e5_v2_phase_f_adapter_contract(tmp_path: Path) -> None:
    decisions_path = tmp_path / "decisions_with_side.csv"
    e5_path = tmp_path / "e5_side_layer.parquet"
    out_path = tmp_path / "decisions_with_side_e5.csv"

    pd.DataFrame(
        {
            "symbol": ["XAUUSD.mg"] * 5,
            "ts": [
                "2025-01-01 00:00:00",
                "2025-01-01 01:00:00",
                "2025-01-01 02:00:00",
                "2025-01-01 03:00:00",
                "2025-01-01 04:00:00",
            ],
            "decision": ["ALLOW", "ALLOW", "ALLOW", "BLOCK", "ALLOW"],
            "setup_family": ["a", "a", "a", "b", "a"],
            "side_intent": ["SHORT", "LONG", "SHORT", "NONE", "LONG"],
        }
    ).to_csv(decisions_path, index=False)

    pd.DataFrame(
        {
            "symbol": ["XAUUSD.mg", "XAUUSD.mg", "XAUUSD.mg"],
            "time": [
                "2025-01-01 00:00:00",
                "2025-01-01 01:00:00",
                "2025-01-01 03:00:00",
            ],
            "e5_has_prediction": [1, 1, 1],
            "e5_side": ["LONG", "ABSTAIN", "SHORT"],
            "e5_long_score": [0.8, 0.2, 0.1],
            "e5_short_score": [0.1, 0.2, 0.8],
            "e5_abstain_score": [0.1, 0.6, 0.1],
            "e5_margin": [0.7, 0.0, -0.7],
            "e5_confidence": [0.9, 0.6, 0.8],
            "e5_model_tag": ["phase_e5_v2", "phase_e5_v2", "phase_e5_v2"],
        }
    ).to_parquet(e5_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase_e5_v2_phase_f_adapter.py",
            "--decisions",
            str(decisions_path),
            "--e5-side-layer",
            str(e5_path),
            "--replace-side-intent",
            "--out-path",
            str(out_path),
        ],
        check=True,
    )

    out = pd.read_csv(out_path)

    assert (out["decision"] == ["ALLOW", "ALLOW", "ALLOW", "BLOCK", "ALLOW"]).all()
    assert out.loc[0, "side_intent_orig"] == "SHORT"
    assert out.loc[0, "side_intent_final"] == "LONG"
    assert out.loc[0, "e5_override_reason"] == "use_e5_side"
    assert out.loc[0, "e5_override_applied"] == 1

    assert out.loc[1, "side_intent_final"] == "LONG"
    assert out.loc[1, "e5_override_reason"] == "fallback_abstain"
    assert out.loc[1, "e5_override_applied"] == 0

    assert out.loc[2, "side_intent_final"] == "SHORT"
    assert out.loc[2, "e5_override_reason"] == "fallback_missing"

    assert out.loc[3, "decision"] == "BLOCK"
    assert out.loc[3, "side_intent_final"] == "NONE"
    assert out.loc[3, "e5_override_reason"] == "no_change_non_allow"

    assert out.loc[4, "side_intent_final"] == "LONG"
    assert out.loc[4, "e5_override_reason"] == "fallback_missing"

    # compatibility mode writes side_intent final value
    assert (out["side_intent"] == out["side_intent_final"]).all()
