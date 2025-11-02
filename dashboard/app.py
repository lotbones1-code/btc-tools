import os
import time
from datetime import datetime
from html import escape

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from quant_core import TZ, add_indicators, classify_signal, latest_snapshot

st.set_page_config(page_title="BTC Quant Dashboard", layout="wide")

# ---------- Sidebar Controls ----------
referral_link_raw = os.getenv("REFERRAL_LINK")
referral_headline = os.getenv(
    "REFERRAL_HEADLINE", "Unlock bonuses with our referral link"
)
referral_subhead = os.getenv(
    "REFERRAL_SUBHEAD",
    "Join with our exclusive invite to trade smarter with real-time signals.",
)
referral_benefit = os.getenv("REFERRAL_BENEFIT")
referral_cta = os.getenv("REFERRAL_CTA", "Get the referral bonus")
referral_disclaimer = os.getenv("REFERRAL_DISCLAIMER")
safe_link = ""
safe_cta = ""

st.sidebar.title("Controls")
timeframe = st.sidebar.selectbox("Timeframe", ["5m", "15m", "1h", "4h", "1d"], index=2)
refresh_s = st.sidebar.slider("Refresh (seconds)", 5, 120, 20, step=5)
show_ema = st.sidebar.checkbox("Show EMA(50/200)", value=True)
show_sma = st.sidebar.checkbox("Show SMA(50/200)", value=True)
st.sidebar.caption("Data source: Kraken via ccxt. Times in America/Denver.")

if referral_link_raw:
    safe_link = escape(referral_link_raw, quote=True)
    safe_cta = escape(referral_cta)
    sidebar_copy = referral_benefit or referral_subhead
    st.sidebar.markdown("---")
    st.sidebar.subheader("Referral perks")
    st.sidebar.markdown(
        f'<a class="referral-sidebar" href="{safe_link}" target="_blank" '
        f'rel="noopener noreferrer">{safe_cta}</a>',
        unsafe_allow_html=True,
    )
    if sidebar_copy:
        st.sidebar.caption(sidebar_copy)

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
    .referral-card {
        margin: 0 0 24px 0;
        padding: 28px;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(16,185,129,0.12));
        border: 1px solid rgba(148,163,184,0.35);
        box-shadow: 0 10px 30px rgba(15,23,42,0.08);
    }
    .referral-card h2 {
        margin: 0 0 12px 0;
        font-size: 28px;
        color: #0f172a;
    }
    .referral-card p {
        margin: 0 0 18px 0;
        font-size: 16px;
        color: #1e293b;
    }
    .referral-benefit {
        font-weight: 600;
    }
    .referral-button {
        display:inline-block;
        padding: 12px 20px;
        border-radius: 999px;
        background: #2563eb;
        color: #fff;
        font-weight: 600;
        text-decoration: none;
        box-shadow: 0 12px 20px rgba(37,99,235,0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .referral-button:hover {
        transform: translateY(-1px);
        box-shadow: 0 16px 24px rgba(37,99,235,0.35);
    }
    .referral-disclaimer {
        margin-top: 12px;
        font-size: 13px;
        color: #475569;
    }
    .referral-sidebar {
        display:inline-block;
        padding:10px 16px;
        border-radius:999px;
        background:#2563eb;
        color:#fff !important;
        font-weight:600;
        text-decoration:none;
        text-align:center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if referral_link_raw:
    safe_headline = escape(referral_headline)
    safe_subhead = escape(referral_subhead)
    benefit_html = (
        f"<p class='referral-benefit'>{escape(referral_benefit)}</p>"
        if referral_benefit
        else ""
    )
    disclaimer_html = (
        f"<p class='referral-disclaimer'>{escape(referral_disclaimer)}</p>"
        if referral_disclaimer
        else ""
    )
    st.markdown(
        f"""
        <section class="referral-card">
            <h2>{safe_headline}</h2>
            <p>{safe_subhead}</p>
            {benefit_html}
            <a class="referral-button" href="{safe_link}" target="_blank" rel="noopener noreferrer">{safe_cta}</a>
            {disclaimer_html}
        </section>
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
