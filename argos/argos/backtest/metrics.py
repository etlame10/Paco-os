"""Métricas de rendimiento. Funciones puras, ya implementadas y testeadas,
para que el futuro motor de backtesting y la comparación contra Buy & Hold
usen exactamente las mismas definiciones."""

from __future__ import annotations

import math

import pandas as pd

from argos.analysis.technical.indicators import TRADING_DAYS, max_drawdown
from argos.backtest.models import BacktestMetrics, Trade


def total_return(equity: pd.Series) -> float:
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def annualized_return(equity: pd.Series, periods_per_year: int = TRADING_DAYS) -> float | None:
    years = (len(equity) - 1) / periods_per_year
    if years <= 0 or equity.iloc[0] <= 0:
        return None
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def volatility(equity: pd.Series, periods_per_year: int = TRADING_DAYS) -> float | None:
    r = equity.pct_change().dropna()
    if len(r) < 2:
        return None
    return float(r.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe(equity: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS) -> float | None:
    r = equity.pct_change().dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return None
    excess = r - risk_free / periods_per_year
    return float(excess.mean() / r.std(ddof=1) * math.sqrt(periods_per_year))


def win_rate(trades: list[Trade]) -> float | None:
    closed = [t for t in trades if t.pnl is not None]
    if not closed:
        return None
    return sum(t.pnl > 0 for t in closed) / len(closed)


def compute_metrics(equity: pd.Series, trades: list[Trade]) -> BacktestMetrics:
    return BacktestMetrics(
        total_return=total_return(equity),
        annualized_return=annualized_return(equity),
        max_drawdown=max_drawdown(equity),
        volatility=volatility(equity),
        sharpe=sharpe(equity),
        n_trades=len(trades),
        win_rate=win_rate(trades),
        profit_loss=float(equity.iloc[-1] - equity.iloc[0]),
    )
