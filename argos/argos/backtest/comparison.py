"""Comparación estrategia vs Buy & Hold.

La pregunta no es "¿ganó dinero?" sino "¿aportó algo frente a simplemente
mantener el activo?". Se compara rentabilidad, riesgo y rentabilidad ajustada
al riesgo, y se añaden advertencias sobre la solidez estadística.
"""

from __future__ import annotations

from argos.backtest.models import Comparison, ComparisonItem, PerformanceMetrics

#: Por debajo de este número de operaciones no hay base estadística razonable.
MIN_TRADES_FOR_EVIDENCE = 30


def _pct(x: float | None) -> str:
    return "n/d" if x is None else f"{x * 100:+.2f}%"


def _item(metric, s, b, higher_is_better, fmt, label):
    if s is None or b is None:
        return ComparisonItem(metric=metric, strategy=s, benchmark=b, difference=None, better=None,
                              text=f"{label}: no comparable (falta algún dato).")
    diff = s - b
    better = None if abs(diff) < 1e-12 else (diff > 0) == higher_is_better
    word = "igual que" if better is None else ("mejor que" if better else "peor que")
    return ComparisonItem(metric=metric, strategy=s, benchmark=b, difference=diff, better=better,
                          text=f"{label}: ARGOS {fmt(s)} vs Buy & Hold {fmt(b)} → {word} mantener el activo.")


def compare(strategy: PerformanceMetrics, benchmark: PerformanceMetrics, *, simulated_data: bool) -> Comparison:
    num = lambda x: f"{x:.2f}"  # noqa: E731
    items = [
        _item("total_return", strategy.total_return, benchmark.total_return, True, _pct, "Rentabilidad total"),
        _item("max_drawdown", strategy.max_drawdown, benchmark.max_drawdown, True, _pct, "Caída máxima"),
        _item("volatility", strategy.volatility, benchmark.volatility, False, _pct, "Volatilidad anualizada"),
        _item("sharpe", strategy.sharpe, benchmark.sharpe, True, num, "Sharpe (rentabilidad por unidad de riesgo)"),
    ]
    by = {i.metric: i for i in items}
    ret_better = by["total_return"].better
    risk_better = by["max_drawdown"].better
    sharpe_better = by["sharpe"].better

    if strategy.n_trades == 0:
        verdict = ("La estrategia no llegó a operar en este periodo: permaneció en liquidez. "
                   "No hay nada que evaluar; el resultado frente a Buy & Hold es solo el de no invertir.")
    elif ret_better and strategy.total_return < 0:
        verdict = ("Ambas perdieron dinero en este periodo; la estrategia perdió MENOS que Buy & Hold. "
                   "Limitó pérdidas, no generó beneficios.")
    elif ret_better and sharpe_better is not False:
        verdict = "En este periodo histórico la estrategia obtuvo más rentabilidad que Buy & Hold."
    elif ret_better is False and sharpe_better:
        verdict = ("La estrategia ganó menos que Buy & Hold, pero con mejor relación rentabilidad/riesgo: "
                   "aportó control del riesgo, no rentabilidad.")
    elif ret_better is False and risk_better:
        verdict = ("La estrategia ganó menos que Buy & Hold y solo redujo la caída máxima. "
                   "No está claro que aporte valor: mantener el activo habría rendido más.")
    elif ret_better is False:
        verdict = "En este periodo histórico la estrategia NO aportó nada frente a simplemente mantener el activo."
    else:
        verdict = "Resultado no concluyente frente a Buy & Hold."

    caveats = []
    if strategy.n_trades < MIN_TRADES_FOR_EVIDENCE:
        caveats.append(
            f"Solo {strategy.n_trades} operación(es) cerrada(s). Con menos de {MIN_TRADES_FOR_EVIDENCE} "
            "el resultado puede deberse al azar: no hay base estadística para afirmar que la regla funciona o falla."
        )
    if strategy.total_return > 0:
        caveats.append("Que la estrategia gane dinero no significa que sea buena: lo relevante es si mejora a mantener el activo con un riesgo comparable.")
    caveats.append("Un único activo y un único periodo. Hace falta repetir la prueba en otros activos y periodos antes de sacar conclusiones.")
    if simulated_data:
        caveats.append("Los datos son SIMULADOS: este resultado solo sirve para comprobar que el motor funciona, no dice nada del mercado real.")
    caveats.append("Resultado histórico, no predicción: no garantiza resultados futuros.")
    return Comparison(items=items, verdict=verdict, caveats=caveats)
