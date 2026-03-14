# state_visual_lab/plot_state_grid.py
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

WINDOWS_PATH = r"outputs/state_visual_lab/US500/windows_by_state_ohlc_vwap.parquet"
OUT_PATH = r"outputs/state_visual_lab/US500/grid_state_0.png"

L = 24
R = 12
N = L + R + 1
MIN_GAP = 37
TARGET_STATE = 0.0
N_PLOTS = 9

STATE_NAME_MAP = {
    0.0: "BALANCE",
    1.0: "TRANSITION",
    2.0: "TREND",
}


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

    for idx, row in df.iterrows():
        a = int(row["anchor_idx"])
        if last_anchor is None or (a - last_anchor) >= min_gap:
            selected.append(idx)
            last_anchor = a
        if len(selected) >= n_plots:
            break

    return df.loc[selected].copy()


def main():
    w = pd.read_parquet(WINDOWS_PATH).copy()
    w = w[w["state_hat"] == TARGET_STATE].sort_values("anchor_idx").reset_index(drop=True)

    picked = select_spaced_rows(w, n_plots=N_PLOTS, min_gap=MIN_GAP)

    print("available rows for state:", len(w))
    print("picked rows:", len(picked))
    print(picked[["anchor_idx", "anchor_time", "state_hat", "quality_label"]])

    fig, axes = plt.subplots(3, 3, figsize=(18, 12))
    axes = axes.flatten()

    x = np.arange(N)

    state_name = STATE_NAME_MAP.get(TARGET_STATE, str(TARGET_STATE))

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
        ql = row.get("quality_label", "NA")
        anchor_idx = int(row["anchor_idx"])

        ax.set_title(f"{anchor_time}\nidx={anchor_idx} | ql={ql}", fontsize=10)
        ax.set_xlim(-1, N)
        ax.grid(True, alpha=0.25)

    for ax in axes[len(picked):]:
        ax.axis("off")

    fig.suptitle(
        f"{state_name} | spaced grid | MIN_GAP={MIN_GAP} | n={len(picked)}",
        fontsize=16
    )

    plt.tight_layout()
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    plt.close()

    print("saved:", OUT_PATH)


if __name__ == "__main__":
    main()