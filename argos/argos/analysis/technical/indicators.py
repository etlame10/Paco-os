"""Indicadores técnicos como funciones puras sobre series de pandas.

Sin interpretación aquí: solo cálculo. Estas mismas funciones se reutilizarán
en estrategias y backtesting, así que un indicador se calcula igual en el
análisis que en la simulación histórica.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder (media exponencial con alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    out = 100 - 100 / (1 + rs)
    # Sin pérdidas en el periodo -> RSI = 100; sin movimiento -> 50.
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def annualized_volatility(close: pd.Series, window: int) -> float | None:
    r = log_returns(close).dropna().tail(window)
    if len(r) < max(2, window // 2):
        return None
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def drawdown(series: pd.Series) -> pd.Series:
    """Caída desde el máximo previo, en tanto por uno (0 = en máximos)."""
    return series / series.cummax() - 1


def max_drawdown(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return float(drawdown(series).min())


def pct_change_over(close: pd.Series, bars: int) -> float | None:
    if len(close) <= bars:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - bars] - 1)


def last(series: pd.Series) -> float | None:
    if series.empty:
        return None
    v = series.iloc[-1]
    return None if pd.isna(v) else float(v)
