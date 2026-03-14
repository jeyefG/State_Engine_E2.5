# state_visual_lab/plot_one_window.py
# state_visual_lab/plot_one_window.py
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

WINDOWS_PATH = r"outputs/state_visual_lab/US500/windows_by_state_ohlc_vwap.parquet"
OUT_PATH = r"outputs/state_visual_lab/US500/one_window_example.png"

L = 24
R = 12
N = L + R + 1  # 37 barras

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


def main():
    w = pd.read_parquet(WINDOWS_PATH)

    row = w.iloc[0]
    window_n = int(row.name)
    anchor_time = pd.to_datetime(row["anchor_time"])
    anchor_time_str = anchor_time.strftime("%Y-%m-%d %H:%M")

    opens = np.array([row[f"open_{j}"] for j in range(N)], dtype=float)
    highs = np.array([row[f"high_{j}"] for j in range(N)], dtype=float)
    lows = np.array([row[f"low_{j}"] for j in range(N)], dtype=float)
    closes = np.array([row[f"close_{j}"] for j in range(N)], dtype=float)
    vwap = np.array([row[f"vwap_{j}"] for j in range(N)], dtype=float)

    x = np.arange(N)  # 0..36

    fig, ax = plt.subplots(figsize=(14, 6))

    # sombreado de toda la ventana
    ax.axvspan(-0.5, L - 0.5, color="gray", alpha=0.12, zorder=0)

    plot_candles(ax, x, opens, highs, lows, closes)
    ax.plot(x, vwap, linewidth=1.8, label="VWAP")

    # líneas guía
    # inicio visual de la ventana = borde izquierdo de la primera vela
    ax.axvline(-0.5, linestyle=":", linewidth=1.2, color="steelblue")
    # ancla = centro de la vela 24
    ax.axvline(L, linestyle="--", linewidth=1.2, color="steelblue")
    # fin visual de la ventana = borde derecho de la última vela
    ax.axvline(N - 0.5, linestyle=":", linewidth=1.2, color="steelblue")

    # título
    state_value = row["state_hat"]
    state_name = STATE_NAME_MAP.get(state_value, str(state_value))
    ql = row.get("quality_label", "NA")
    
    ax.set_title(
        f"window #{window_n} | {anchor_time_str} | state_hat={state_name} | quality_label={ql}"
    )

    ax.set_xlabel("bar index in window")
    ax.set_ylabel("normalized return vs anchor close")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # etiquetas abajo
    ymin, ymax = ax.get_ylim()
    ax.text(-0.5, ymin, "window start", ha="left", va="top")
    ax.text(L, ymin, "anchor (bar 24)", ha="center", va="top")
    ax.text(N - 0.5, ymin, "window end", ha="right", va="top")

    # ticks un poco más claros
    ax.set_xlim(-1, N)
    ax.set_xticks(np.arange(0, N, 5))

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    plt.close()

    print("saved:", OUT_PATH)
    print("N bars:", N)
    print("anchor index:", L)
    print("left tail bars:", L)
    print("right tail bars:", R)
    print("window_n:", window_n)
    print("anchor_time:", anchor_time_str)


if __name__ == "__main__":
    main()