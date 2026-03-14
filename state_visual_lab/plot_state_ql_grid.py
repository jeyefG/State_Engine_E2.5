# state_visual_lab/plot_state_ql_grid.py
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

WINDOWS_PATH = r"outputs/state_visual_lab/US500/windows_by_state_ohlc_vwap.parquet"
OUT_DIR = r"outputs/state_visual_lab/US500"

L = 24
R = 12
N = L + R + 1

STATE_NAME_MAP = {
    0.0: "BALANCE",
    1.0: "TRANSITION",
    2.0: "TREND",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=float, required=True, help="state_hat value, e.g. 0 1 2")
    parser.add_argument("--ql", type=str, required=True, help="quality_label value")
    parser.add_argument("--n_plots", type=int, default=9, help="number of windows to plot")
    parser.add_argument("--min_gap", type=int, default=37, help="minimum anchor_idx gap between selected windows")
    return parser.parse_args()


def plot_candles(ax, x, opens, highs, lows, closes, width=0.6):
    for xi, o, h, l, c in zip(x, opens, highs, lows, closes):
        color = "green" if c >= o else "red"
        ax.vlines(xi, l, h, linewidth=1, color=color)

        body_low = min(o, c)
        body_h = abs(c - o)
        if body_h == 0:
            body_h = 1e-6

        rect = Rectangle(
            (xi - width / 2, body_low),
            width,
            body_h,
            facecolor=color,
            edgecolor=color,
            alpha=0.35,
            linewidth=1,
        )
        ax.add_patch(rect)


def select_spaced_rows(df, n_plots, min_gap):
    selected = []
    last_anchor = None

    for _, row in df.iterrows():
        a = int(row["anchor_idx"])
        if last_anchor is None or (a - last_anchor) >= min_gap:
            selected.append(row)
            last_anchor = a
        if len(selected) >= n_plots:
            break

    if not selected:
        return pd.DataFrame(columns=df.columns)

    return pd.DataFrame(selected)


def main():
    args = parse_args()

    w = pd.read_parquet(WINDOWS_PATH).copy()

    w = w[
        (w["state_hat"] == args.state) &
        (w["quality_label"] == args.ql)
    ].sort_values("anchor_idx").reset_index(drop=True)

    picked = select_spaced_rows(w, n_plots=args.n_plots, min_gap=args.min_gap)

    print("available rows:", len(w))
    print("picked rows:", len(picked))
    if len(picked) > 0:
        print(picked[["anchor_idx", "anchor_time", "state_hat", "quality_label"]])

    n = len(picked)
    ncols = 3
    nrows = int(np.ceil(max(n, 1) / ncols))

    fig, axes = plt.subplots(nrows, ncols, figsize=(18, 4 * nrows))
    axes = np.atleast_1d(axes).flatten()
    x = np.arange(N)

    state_name = STATE_NAME_MAP.get(args.state, str(args.state))

    for ax, (_, row) in zip(axes, picked.iterrows()):
        opens = np.array([row[f"open_{j}"] for j in range(N)], dtype=float)
        highs = np.array([row[f"high_{j}"] for j in range(N)], dtype=float)
        lows = np.array([row[f"low_{j}"] for j in range(N)], dtype=float)
        closes = np.array([row[f"close_{j}"] for j in range(N)], dtype=float)
        vwap = np.array([row[f"vwap_{j}"] for j in range(N)], dtype=float)

        ax.axvspan(-0.5, L - 0.5, color="gray", alpha=0.12, zorder=0)
        plot_candles(ax, x, opens, highs, lows, closes)
        ax.plot(x, vwap, linewidth=1.5)

        ax.axvline(-0.5, linestyle=":", linewidth=1.0, color="steelblue")
        ax.axvline(L, linestyle="--", linewidth=1.0, color="steelblue")
        ax.axvline(N - 0.5, linestyle=":", linewidth=1.0, color="steelblue")

        anchor_time = pd.to_datetime(row["anchor_time"]).strftime("%Y-%m-%d %H:%M")
        anchor_idx = int(row["anchor_idx"])

        ax.set_title(f"{anchor_time}\nidx={anchor_idx}", fontsize=10)
        ax.set_xlim(-1, N)
        ax.grid(True, alpha=0.25)

    for ax in axes[len(picked):]:
        ax.axis("off")

    safe_ql = args.ql.replace("/", "_").replace(" ", "_")
    out_path = Path(OUT_DIR) / f"grid_state_{int(args.state)}__ql_{safe_ql}.png"

    fig.suptitle(
        f"{state_name} + {args.ql} | MIN_GAP={args.min_gap} | n={len(picked)}",
        fontsize=16
    )
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()

    print("saved:", out_path)


if __name__ == "__main__":
    main()