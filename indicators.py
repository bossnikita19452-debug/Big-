import pandas as pd
import pandas_ta_classic as ta


def calculate_ema(df: pd.DataFrame, length: int) -> pd.Series:
    """EMA с указанным периодом."""
    return ta.ema(df["close"], length=length)


def calculate_rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """RSI с указанным периодом."""
    return ta.rsi(df["close"], length=length)


def calculate_macd(df: pd.DataFrame):
    """MACD: линия, сигнальная, гистограмма."""
    macd = ta.macd(df["close"])
    return macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]  # macd, signal, hist


def calculate_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """ATR для оценки волатильности."""
    return ta.atr(df["high"], df["low"], df["close"], length=length)