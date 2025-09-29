import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from quant_core import TZ, add_indicators, classify_signal, latest_snapshot

st.set_page_config(page_title="BTC Quant Dashboard", layout="wide")

# ---------- Sidebar Controls ----------
st.sidebar.title("Controls")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h", "4h", "1d"], index=2)
refresh_s = st.sidebar.slider("Refresh (seconds)", 5, 120, 20, step=5)
show_ema = st.sidebar.checkbox("Show EMA(50/200)", value=True)
show_sma = st.sidebar.checkbox("Show SMA(50/200)", value=True)
st.sidebar.caption("Data source: Kraken via ccxt. Times in America/Denver.")

# ---------- Header ----------
st.markdown(
    """
    <style>
    .sig-badge {
        display:inline-block; padding:10px 16px; border-radius:12px;
        font-weight:700; font-size:22px; margin-right:12px;
    }
    .bull { background:#e7f7ed; color:#137333; border:1px solid #b7e3c7; }
    .bear { background:#fde8e7; color:#a50e0e; border:1px solid #f6c1bf; }
    .neutral { background:#eef2f7; color:#334155; border:1px solid #cbd5e1; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Data fetch ----------
if "snapshot" not in st.session_state:
    st.session_state["snapshot"] = None
    st.session_state["snapshot_timeframe"] = None
    st.session_state["snapshot_cached_at"] = None

if st.session_state["snapshot_timeframe"] != timeframe:
    st.session_state["snapshot"] = None
    st.session_state["snapshot_cached_at"] = None
    st.session_state["snapshot_timeframe"] = timeframe

error_message = None

try:
    snapshot = latest_snapshot(timeframe)
    st.session_state["snapshot"] = snapshot
    st.session_state["snapshot_cached_at"] = datetime.now(TZ)
except Exception as exc:  # noqa: BLE001 - we want to show any failure to the user
    error_message = str(exc)
    snapshot = st.session_state.get("snapshot")

if snapshot is None:
    st.error("Unable to load market data right now. Retrying shortly...")
    if error_message:
        st.caption(error_message)
    time.sleep(refresh_s)
    st.experimental_rerun()

df, sig, now = snapshot

if error_message:
    cached_at = st.session_state.get("snapshot_cached_at")
    if cached_at is not None:
        st.warning(
            "Showing cached data from "
            f"{cached_at.strftime('%Y-%m-%d %H:%M:%S %Z')} due to a fetch error."
        )
        st.caption(error_message)

last = df.iloc[-1]
close_val = float(last["close"])
rsi_val = float(last["RSI"])
macd_val = float(last["MACD"])
macds_val = float(last["MACDSignal"])

# ---------- Top row KPIs ----------
col1, col2, col3, col4 = st.columns([1.4, 1, 1, 1])
badge_class = "bull" if sig == "Bullish" else ("bear" if sig == "Bearish" else "neutral")
with col1:
    st.markdown(f'<span class="sig-badge {badge_class}">Signal: {sig}</span>', unsafe_allow_html=True)
    st.caption(f"Updated: {now}")
with col2:
    st.metric("Close (USD)", f"{close_val:,.2f}")
with col3:
    st.metric("RSI (14)", f"{rsi_val:,.1f}")
with col4:
    trend_txt = "Above" if macd_val > macds_val else "Below"
    st.metric("MACD vs Signal", trend_txt, delta=f"{(macd_val - macds_val):.2f}")

st.divider()

# ---------- Chart ----------
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3],
    vertical_spacing=0.05,
)

# Price
fig.add_trace(go.Scatter(x=df.index, y=df["close"], name="Price", mode="lines"), row=1, col=1)

if show_sma:
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], name="SMA50", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], name="SMA200", mode="lines"), row=1, col=1)

if show_ema:
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA50"], name="EMA50", mode="lines"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["EMA200"], name="EMA200", mode="lines"), row=1, col=1)

# RSI
fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", mode="lines"), row=2, col=1)
fig.add_hline(y=70, line_dash="dot", row=2, col=1)
fig.add_hline(y=30, line_dash="dot", row=2, col=1)

fig.update_layout(
    height=600,
    margin=dict(l=40, r=20, t=40, b=40),
    legend=dict(orientation="h", y=1.02, x=0),
)
fig.update_xaxes(showgrid=False)
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="rgba(148,163,184,.25)")

st.plotly_chart(fig, use_container_width=True)

# ---------- Data + Export ----------
st.subheader("Latest rows")
st.dataframe(df.tail(10)[["close", "SMA50", "SMA200", "EMA50", "EMA200", "RSI", "MACD", "MACDSignal"]])

csv = df.to_csv().encode("utf-8")
st.download_button(
    "Download CSV", csv, file_name=f"btc_{timeframe}_signals.csv", mime="text/csv"
)

# ---------- Auto refresh ----------
st.caption("Auto-refresh is enabled; page will update on interval.")
time.sleep(refresh_s)
st.experimental_rerun()
