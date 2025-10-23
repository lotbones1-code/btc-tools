"""Core quantitative utilities shared by the CLI and dashboard applications."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import ccxt
import pandas as pd
import pytz
import yaml

TZ = pytz.timezone("America/Denver")


def load_settings(path: str | Path | None = None) -> Dict[str, Any]:
    """Load YAML settings from ``conf/settings.yml``.

    Parameters
    ----------
    path:
        Optional override for the settings file location.
    """

    if path is None:
        path = Path(__file__).resolve().parent / "conf" / "settings.yml"
    else:
        path = Path(path)

    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _get_exchange_and_symbol(exchange_id: str, symbol: str) -> Tuple[ccxt.Exchange, str]:
    """Instantiate an exchange client and validate the requested symbol."""

    try:
        exchange_cls = getattr(ccxt, exchange_id.lower())
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Exchange '{exchange_id}' is not supported by ccxt.") from exc

    exchange = exchange_cls({"enableRateLimit": True})
    exchange.load_markets()

    if symbol not in exchange.symbols:
        base, _, quote = symbol.partition("/")
        # Allow common BTC base symbol aliases when a direct match is missing.
        btc_aliases = {
            "BTC": ["XBT"],
            "XBT": ["BTC"],
        }
        for alt_base in btc_aliases.get(base.upper(), []):
            candidate = f"{alt_base}/{quote}" if quote else alt_base
            if candidate in exchange.symbols:
                symbol = candidate
                break
        else:
            raise ValueError(
                f"Symbol '{symbol}' is not available on exchange '{exchange_id}'."
            )

    return exchange, symbol


def fetch_ohlcv(
    timeframe: str = "1h",
    limit: int = 500,
    *,
    exchange_id: str = "kraken",
    symbol: str = "BTC/USD",
) -> pd.DataFrame:
    """Fetch OHLCV data and return it as a timezone-aware dataframe."""

    exchange, resolved_symbol = _get_exchange_and_symbol(exchange_id, symbol)
    ohlcv = exchange.fetch_ohlcv(resolved_symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True).dt.tz_convert(TZ)
    df.set_index("time", inplace=True)
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Append common trend and momentum indicators to *df*."""

    df = df.copy()

    # SMAs
    df["SMA50"] = df["close"].rolling(50).mean()
    df["SMA200"] = df["close"].rolling(200).mean()

    # EMAs
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI (Wilder's smoothing, period 14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100)
    rsi = rsi.where(avg_gain != 0, 0)
    df["RSI"] = rsi

    # MACD (12,26,9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACDSignal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACDHist"] = df["MACD"] - df["MACDSignal"]

    return df


def classify_signal(row: pd.Series) -> str:
    """Return a coarse market regime classification for the latest row."""

    sma_bull = row["SMA50"] > row["SMA200"]
    sma_bear = row["SMA50"] < row["SMA200"]
    ema_bull = row["EMA50"] > row["EMA200"]
    ema_bear = row["EMA50"] < row["EMA200"]
    rsi_bull = row["RSI"] > 50
    rsi_bear = row["RSI"] < 50
    macd_bull = row["MACD"] > row["MACDSignal"]
    macd_bear = row["MACD"] < row["MACDSignal"]

    bull_votes = sum([sma_bull, ema_bull, rsi_bull, macd_bull])
    bear_votes = sum([sma_bear, ema_bear, rsi_bear, macd_bear])

    if bull_votes >= 3 and bull_votes > bear_votes:
        return "Bullish"
    if bear_votes >= 3 and bear_votes > bull_votes:
        return "Bearish"
    return "Neutral"


def latest_snapshot(
    timeframe: str = "1h",
    limit: int = 500,
    *,
    exchange_id: str = "kraken",
    symbol: str = "BTC/USD",
) -> tuple[pd.DataFrame, str, str]:
    df = add_indicators(
        fetch_ohlcv(
            timeframe=timeframe,
            limit=limit,
            exchange_id=exchange_id,
            symbol=symbol,
        )
    )
    last = df.iloc[-1]
    sig = classify_signal(last)
    now = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    return df, sig, now


def main():
    parser = argparse.ArgumentParser(description="BTC Quant CLI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--live", action="store_true", help="Run live signal snapshot")
    group.add_argument("--backtest", type=int, metavar="DAYS", help="Run backtest stub for DAYS")
    group.add_argument("--test", action="store_true", help="Run CLI self-test")
    parser.add_argument(
        "--report",
        nargs="?",
        const="",
        default=None,
        help="Generate report folder (optional path)",
    )
    args = parser.parse_args()

    if args.test:
        print(">>> Codex Sync Test OK <<<")
        return

    settings = load_settings()
    exchange_id = settings.get("exchange", "kraken")
    symbol = settings.get("symbol", "BTC/USD")

    if args.report is not None:
        base = args.report or settings.get("logging", {}).get("dir", "logs")
        timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
        report_dir = Path(base) / timestamp
        report_dir.mkdir(parents=True, exist_ok=True)
        with open(report_dir / "config_used.yml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(settings, fh)

    timeframe = settings.get("timeframe", "1h")
    limit = settings.get("limit", 500)

    if args.live:
        df = add_indicators(
            fetch_ohlcv(
                timeframe=timeframe,
                limit=limit,
                exchange_id=exchange_id,
                symbol=symbol,
            )
        )
        sig = classify_signal(df.iloc[-1])
        print(sig)
        return

    if args.backtest is not None:
        print(f"Backtest stub DAYS={args.backtest}")
        return

    # Default behavior
    df, sig, now = latest_snapshot(
        timeframe=timeframe,
        limit=limit,
        exchange_id=exchange_id,
        symbol=symbol,
    )
    print(df.tail())
    print(f"Signal: {sig} at {now}")


if __name__ == "__main__":
    main()
