from pathlib import Path
import subprocess
import sys

import pandas as pd


def test_phase_e5_v2_side_layer_adapter_episode_fill(tmp_path: Path) -> None:
    context_path = tmp_path / "context.parquet"
    scores_path = tmp_path / "scores.parquet"
    out_path = tmp_path / "e5_side_layer.parquet"

    context = pd.DataFrame(
        {
            "symbol": ["XAUUSD.mg"] * 6,
            "time": pd.to_datetime(
                [
                    "2025-01-01 00:00:00",
                    "2025-01-01 01:00:00",
                    "2025-01-01 02:00:00",
                    "2025-01-01 03:00:00",
                    "2025-01-01 04:00:00",
                    "2025-01-01 05:00:00",
                ]
            ),
            "state_hat": [0, 0, 0, 1, 1, 1],
            "quality_label": ["BALANCE_STABLE", "BALANCE_STABLE", "BALANCE_STABLE", "TREND_CLEAN", "TREND_CLEAN", "TREND_CLEAN"],
            "LOOK_FOR_ALPHA": [1, 1, 1, 1, 1, 1],
        }
    )
    context.to_parquet(context_path, index=False)

    scores = pd.DataFrame(
        {
            "symbol": ["XAUUSD.mg", "XAUUSD.mg"],
            "time": pd.to_datetime(["2025-01-01 00:00:00", "2025-01-01 03:00:00"]),
            "e5_long_score": [0.8, 0.2],
            "e5_short_score": [0.1, 0.7],
            "e5_abstain_score": [0.1, 0.1],
            "e5_margin": [0.7, -0.5],
            "e5_confidence": [0.8, 0.7],
            "e5_recommended_side": ["LONG", "SHORT"],
        }
    )
    scores.to_parquet(scores_path, index=False)

    subprocess.run(
        [
            sys.executable,
            "scripts/build_phase_e5_v2_side_layer.py",
            "--context-parquet",
            str(context_path),
            "--scores-parquet",
            str(scores_path),
            "--out-path",
            str(out_path),
            "--context-tf",
            "H1",
        ],
        check=True,
    )

    out = pd.read_parquet(out_path)

    assert len(out) == len(context)
    assert out["e5_is_episode_start"].sum() == 2
    assert set(out.columns) >= {
        "symbol",
        "time",
        "e5_episode_id",
        "e5_is_episode_start",
        "e5_has_prediction",
        "e5_side",
        "e5_long_score",
        "e5_short_score",
        "e5_abstain_score",
        "e5_margin",
        "e5_confidence",
        "e5_model_tag",
        "e5_side_threshold",
        "e5_abstain_threshold",
        "e5_margin_threshold",
    }

    assert (out.loc[0:2, "e5_side"] == "LONG").all()
    assert (out.loc[3:5, "e5_side"] == "SHORT").all()
    assert out["e5_has_prediction"].sum() == 2
