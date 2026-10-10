"""Métricas de rendimiento. Funciones puras con definiciones explícitas.

Estrategia y Buy & Hold se miden con EXACTAMENTE las mismas funciones.
"""

from __future__ import annotations

import math

import pandas as pd

from argos.analysis.technical.indicators import TRADING_DAYS, max_drawdown
from argos.backtest.models import PerformanceMetrics, SimulationResult, Trade

#: Mínimo de rendimientos diarios para dar volatilidad y Sharpe.
MIN_RETURNS_FOR_RISK = 60
#: Días naturales mínimos para anualizar la rentabilidad.
MIN_DAYS_TO_ANNUALIZE = 365


def total_return(equity: pd.Series) -> float:
    return float(equity.iloc[-1] / equity.iloc[0] - 1)


def annualized_return(equity: pd.Series) -> float | None:
    """CAGR con días NATURALES entre la primera y la última fecha (requiere índice de fechas)."""
    days = (equity.index[-1] - equity.index[0]).days
    if days < MIN_DAYS_TO_ANNUALIZE or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return None
    return float((equity.iloc[-1] / equity.iloc[0]) ** (365.25 / days) - 1)


def daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def volatility(equity: pd.Series) -> float | None:
    r = daily_returns(equity)
    if len(r) < MIN_RETURNS_FOR_RISK:
        return None
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def sharpe(equity: pd.Series, risk_free: float = 0.0) -> float | None:
    """Sharpe anualizado = media(r − rf/252) / desv(r) × √252, con rendimientos diarios."""
    r = daily_returns(equity)
    if len(r) < MIN_RETURNS_FOR_RISK:
        return None
    sd = r.std(ddof=1)
    if sd == 0 or not math.isfinite(sd):
        return None
    return float((r - risk_free / TRADING_DAYS).mean() / sd * math.sqrt(TRADING_DAYS))


def win_rate(trades: list[Trade]) -> float | None:
    if not trades:
        return None
    return sum(t.pnl > 0 for t in trades) / len(trades)


def equity_series(sim: SimulationResult) -> pd.Series:
    return pd.Series(
        [p.equity for p in sim.equity_curve],
        index=pd.to_datetime([p.date for p in sim.equity_curve]),
        dtype=float,
    )


def compute_metrics(sim: SimulationResult) -> PerformanceMetrics:
    equity = equity_series(sim)
    trades = sim.trades
    initial = sim.config.initial_capital
    # El motor nunca ejecuta en la primera sesión, así que la curva ya empieza en el capital inicial.
    curve = equity
    ann = annualized_return(curve)
    sh = sharpe(curve)
    n_ret = len(daily_returns(curve))
    if sh is not None:
        sharpe_note = f"Tasa libre de riesgo supuesta 0%. Calculado con {n_ret} rendimientos diarios."
    elif n_ret < MIN_RETURNS_FOR_RISK:
        sharpe_note = f"No calculable: hacen falta al menos {MIN_RETURNS_FOR_RISK} sesiones (hay {n_ret})."
    else:
        sharpe_note = "No calculable: el capital no varió (sin volatilidad)."
    in_market = sum(p.position_qty > 0 for p in sim.equity_curve)
    returns = [t.return_pct for t in trades]
    return PerformanceMetrics(
        initial_capital=initial,
        final_capital=sim.final_equity,
        total_return=sim.final_equity / initial - 1,
        annualized_return=ann,
        annualized_return_note=None if ann is not None else f"No se anualiza: periodo inferior a {MIN_DAYS_TO_ANNUALIZE} días.",
        max_drawdown=max_drawdown(curve),
        volatility=volatility(curve),
        sharpe=sh,
        sharpe_note=sharpe_note,
        n_trades=len(trades),
        win_rate=win_rate(trades),
        avg_trade_pnl=(sum(t.pnl for t in trades) / len(trades)) if trades else None,
        avg_trade_return=(sum(returns) / len(returns)) if returns else None,
        best_trade_return=max(returns) if returns else None,
        worst_trade_return=min(returns) if returns else None,
        exposure=in_market / len(sim.equity_curve),
        total_costs=sim.total_commission + sim.total_slippage,
    )
