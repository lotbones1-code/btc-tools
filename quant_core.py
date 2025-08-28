# Shared core logic used by both Streamlit and Colab
import ccxt
import pandas as pd
from datetime import datetime
import pytz

TZ = pytz.timezone('America/Denver')


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


def latest_snapshot(timeframe='1h'):
    df = add_indicators(fetch_ohlcv(timeframe))
    last = df.iloc[-1]
    sig = classify_signal(last)
    now = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
    return df, sig, now
