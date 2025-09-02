# Shared core logic used by both Streamlit and Colab
import argparse
import ccxt
import pandas as pd
import pytz
import yaml
from datetime import datetime
from pathlib import Path

TZ = pytz.timezone('America/Denver')


def load_settings(path: str | None = None):
    """Load YAML settings from conf/settings.yml."""
    if path is None:
        path = Path(__file__).resolve().parent / "conf" / "settings.yml"
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _exchange():
    ex = ccxt.kraken({'enableRateLimit': True})
    ex.load_markets()
    market = 'BTC/USD' if 'BTC/USD' in ex.symbols else 'XBT/USD'
    return ex, market


def fetch_ohlcv(timeframe='1h', limit=500):
    ex, market = _exchange()
    ohlcv = ex.fetch_ohlcv(market, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True).dt.tz_convert(TZ)
    df.set_index('time', inplace=True)
    return df


def add_indicators(df):
    df = df.copy()

    # SMAs
    df['SMA50'] = df['close'].rolling(50).mean()
    df['SMA200'] = df['close'].rolling(200).mean()

    # EMAs
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['close'].ewm(span=200, adjust=False).mean()

    # RSI (14)
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD (12,26,9)
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACDSignal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACDHist'] = df['MACD'] - df['MACDSignal']

    return df


def classify_signal(row):
    sma_bull = row['SMA50'] > row['SMA200']
    sma_bear = row['SMA50'] < row['SMA200']
    ema_bull = row['EMA50'] > row['EMA200']
    ema_bear = row['EMA50'] < row['EMA200']
    rsi_bull = row['RSI'] >= 50
    rsi_bear = row['RSI'] <= 50
    macd_bull = row['MACD'] > row['MACDSignal']
    macd_bear = row['MACD'] < row['MACDSignal']

    bull_votes = sum([sma_bull, ema_bull, rsi_bull, macd_bull])
    bear_votes = sum([sma_bear, ema_bear, rsi_bear, macd_bear])

    if bull_votes >= 3 and bull_votes > bear_votes:
        return 'Bullish'
    if bear_votes >= 3 and bear_votes > bull_votes:
        return 'Bearish'
    return 'Neutral'


def latest_snapshot(timeframe='1h', limit=500):
    df = add_indicators(fetch_ohlcv(timeframe, limit=limit))
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
        df = add_indicators(fetch_ohlcv(timeframe=timeframe, limit=limit))
        sig = classify_signal(df.iloc[-1])
        print(sig)
        return

    if args.backtest is not None:
        print(f"Backtest stub DAYS={args.backtest}")
        return

    # Default behavior
    df, sig, now = latest_snapshot(timeframe=timeframe, limit=limit)
    print(df.tail())
    print(f"Signal: {sig} at {now}")


if __name__ == "__main__":
    main()
