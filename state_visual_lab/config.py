# state_visual_lab/config.py

PARQUET_PATH = r"outputs/phase_f_enriched/phase_d_context_base_US500.spot.mg_H2_2023-01-01_2025-12-31_with_ohlc_vwapbands.parquet"
OUT_DIR = r"outputs/state_visual_lab/US500"

TIME_COL = "time"
PRICE_COL = "close"
STATE_COL = "state_hat"
VWAP_COL = "ctx_vwap"

QL_COL = "quality_label"
LF_PREFIX = "LOOK_FOR_"

L = 24
R = 12

NORMALIZATION = "anchor_return"