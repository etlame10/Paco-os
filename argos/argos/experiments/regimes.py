"""Comportamiento por régimen de mercado (alcista / bajista / lateral).

Se usa la MISMA simulación del periodo (no se reinicia por año): de las curvas
de capital de la estrategia y de Buy & Hold se extrae la rentabilidad de cada
año natural, y el año se clasifica según la rentabilidad de Buy & Hold con
umbrales fijados en el protocolo antes de ver resultados.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel

from argos.backtest.models import BacktestReport

MIN_SESSIONS_FULL_YEAR = 200


class YearResult(BaseModel):
    ticker: str
    period_name: str
    year: int
    regime: str
    strategy_return: float
    benchmark_return: float
    difference: float
    strategy_invested_share: float


def classify(benchmark_return: float, bull: float, bear: float) -> str:
    if benchmark_return > bull:
        return "alcista"
    if benchmark_return < bear:
        return "bajista"
    return "lateral"


def yearly_results(report: BacktestReport, period_name: str, bull: float, bear: float) -> list[YearResult]:
    s = report.strategy.simulation.equity_curve
    b = report.benchmark.simulation.equity_curve
    idx = pd.to_datetime([p.date for p in s])
    eq_s = pd.Series([p.equity for p in s], index=idx)
    eq_b = pd.Series([p.equity for p in b], index=idx)
    pos = pd.Series([p.position_qty > 0 for p in s], index=idx)
    out = []
    for year in sorted(set(idx.year)):
        mask = idx.year == year
        if mask.sum() < MIN_SESSIONS_FULL_YEAR:
            continue  # año incompleto: no se clasifica
        # Rentabilidad del año: desde el último cierre del año anterior (o el capital inicial).
        prev = idx[idx.year < year]
        base_s = eq_s[prev[-1]] if len(prev) else report.strategy.metrics.initial_capital
        base_b = eq_b[prev[-1]] if len(prev) else report.benchmark.metrics.initial_capital
        rs = float(eq_s[mask].iloc[-1] / base_s - 1)
        rb = float(eq_b[mask].iloc[-1] / base_b - 1)
        out.append(YearResult(
            ticker=report.ticker, period_name=period_name, year=year, regime=classify(rb, bull, bear),
            strategy_return=rs, benchmark_return=rb, difference=rs - rb,
            strategy_invested_share=float(pos[mask].mean()),
        ))
    return out


class RegimeSummary(BaseModel):
    regime: str
    n_years: int
    mean_strategy_return: float | None
    mean_benchmark_return: float | None
    years_strategy_better: int


def summarize_regimes(years: list[YearResult]) -> list[RegimeSummary]:
    out = []
    for regime in ("alcista", "bajista", "lateral"):
        ys = [y for y in years if y.regime == regime]
        n = len(ys)
        out.append(RegimeSummary(
            regime=regime,
            n_years=n,
            mean_strategy_return=sum(y.strategy_return for y in ys) / n if n else None,
            mean_benchmark_return=sum(y.benchmark_return for y in ys) / n if n else None,
            years_strategy_better=sum(y.difference > 0 for y in ys),
        ))
    return out
