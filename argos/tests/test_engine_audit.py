"""Auditoría del motor (fase 4): propiedades matemáticas con ejemplos SINTÉTICOS pequeños.

Ningún test usa datos reales ni dice nada sobre rentabilidad.
"""

import json
import math
import random
import shutil
from datetime import date

import pandas as pd
import pytest

from argos.analysis.technical.indicators import sma
from argos.backtest.engine import Backtester, SimulationError
from argos.backtest.metrics import compute_metrics
from argos.backtest.models import BacktestConfig
from argos.strategy.base import Signal, SignalAction
from argos.strategy.examples import SmaCrossover
from tests import synthetic_tiingo as syn
from tests.conftest import make_df


def ohlc(opens, closes):
    idx = pd.bdate_range("2024-01-01", periods=len(opens))
    return pd.DataFrame({"open": opens, "high": [max(o, c) for o, c in zip(opens, closes)],
                         "low": [min(o, c) for o, c in zip(opens, closes)], "close": closes,
                         "volume": [1.0] * len(opens)}, index=idx)


# ----------------------------------------------------------------- medias y calentamiento


def test_sma_matches_naive_definition_and_warmup():
    rng = random.Random(3)
    closes = [100 + rng.gauss(0, 5) for _ in range(260)]
    s50, s200 = sma(pd.Series(closes), 50), sma(pd.Series(closes), 200)
    assert s50.iloc[:49].isna().all() and not math.isnan(s50.iloc[49])
    assert s200.iloc[:199].isna().all() and not math.isnan(s200.iloc[199])
    for i in (49, 120, 199, 259):
        assert s50.iloc[i] == pytest.approx(sum(closes[i - 49:i + 1]) / 50)
    for i in (199, 230, 259):
        assert s200.iloc[i] == pytest.approx(sum(closes[i - 199:i + 1]) / 200)


def test_warmup_boundary_first_possible_signal():
    """Rápida 2 / lenta 5: la lenta existe desde la sesión 4 (índice); el primer CRUCE posible es en la 5."""
    closes = [10, 10, 10, 10, 10, 20]
    df = make_df(closes)
    sig = SmaCrossover(fast=2, slow=5).generate_signals(df)
    assert [(s.date, s.action) for s in sig] == [(df.index[5].date(), SignalAction.ENTER_LONG)]
    assert SmaCrossover(fast=2, slow=5).min_bars == 6 == len(df)
    assert SmaCrossover(fast=2, slow=5).generate_signals(df.iloc[:5]) == []
    assert SmaCrossover().min_bars == 201  # 50/200 del protocolo: 200 para la media + 1 para el cruce


def test_signal_is_not_issued_on_first_valid_bar_even_if_fast_above_slow():
    """La regla solo actúa en CRUCES: si la rápida ya está encima al empezar, no hay señal (así se definió)."""
    df = make_df([float(x) for x in range(1, 40)])
    assert SmaCrossover(fast=2, slow=5).generate_signals(df) == []


# ----------------------------------------------------------------- escala y ajustes hacia atrás


def test_signals_and_returns_are_invariant_to_price_scale():
    rng = random.Random(5)
    closes = [50 * math.exp(0.02 * math.sin(i / 9) + rng.gauss(0, 0.01)) for i in range(400)]
    df = make_df(closes)
    scaled = df.copy()
    scaled[["open", "high", "low", "close"]] *= 0.137
    s1 = SmaCrossover(fast=10, slow=30).generate_signals(df)
    s2 = SmaCrossover(fast=10, slow=30).generate_signals(scaled)
    assert [(x.date, x.action) for x in s1] == [(x.date, x.action) for x in s2] and s1
    cfg = BacktestConfig(commission_pct=0.001, slippage_pct=0.0005)
    r1 = compute_metrics(Backtester().simulate(df, s1, cfg))
    r2 = compute_metrics(Backtester().simulate(scaled, s2, cfg))
    assert r1.total_return == pytest.approx(r2.total_return, rel=1e-12)
    assert r1.max_drawdown == pytest.approx(r2.max_drawdown, rel=1e-12)


def test_back_adjusted_series_does_not_leak_future_into_signals():
    """El ajuste hacia atrás usa eventos FUTUROS para escalar el pasado. Como el cruce de medias solo
    compara precios entre sí, las señales hasta t deben ser idénticas a las calculadas con una serie
    ajustada SOLO con los eventos conocidos en t (ajuste 'en el momento')."""
    rows, _ = syn.build(start=date(2010, 1, 4), end=date(2016, 12, 30), seed=21)
    idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in rows])
    raw = pd.Series([r["close"] for r in rows], index=idx)
    m = pd.Series([1.0] * len(rows), index=idx)  # multiplicador de cada evento en su fecha ex
    for i in range(1, len(rows)):
        r = rows[i]
        if r["divCash"] > 0 or r["splitFactor"] != 1:
            m.iloc[i] = (1 - r["divCash"] / rows[i - 1]["close"]) / r["splitFactor"]
    full_factor = pd.Series([r["f"] for r in rows], index=idx)
    back_adjusted = raw * full_factor
    strat = SmaCrossover(fast=10, slow=40)

    def signals(close):
        df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1.0})
        return [(s.date, s.action) for s in strat.generate_signals(df)]

    full = signals(back_adjusted)
    assert len(full) >= 4
    split_i = next(i for i, r in enumerate(rows) if r["splitFactor"] != 1)
    for t in sorted({split_i - 1, split_i, split_i + 5, 300, 900, len(rows) - 1}):
        # Factor "en el momento t": solo eventos con fecha ex <= t.
        known = m.iloc[: t + 1]
        pit_factor = known[::-1].cumprod()[::-1].shift(-1, fill_value=1.0)
        pit = raw.iloc[: t + 1] * pit_factor
        cut = idx[t].date()
        assert signals(pit) == [s for s in full if s[0] <= cut], f"diferencia al cortar en {cut}"


def test_dividends_are_counted_once_through_adjusted_prices():
    """El rendimiento de la serie ajustada = rendimiento con dividendos reinvertidos (una sola vez).
    El motor no tiene ninguna lógica de dividendos: los CSV de ARGOS no contienen divCash."""
    rows, text = syn.build(start=date(2012, 1, 3), end=date(2016, 12, 30), seed=9)
    adj = [r["close"] * r["f"] for r in rows]
    total_return_adj = adj[-1] / adj[0]
    # Convención del ajuste multiplicativo (tipo CRSP): en la fecha ex, rendimiento = C_t·split / (C_{t−1} − D).
    manual = alt = 1.0
    for prev, cur in zip(rows, rows[1:]):
        manual *= cur["close"] * cur["splitFactor"] / (prev["close"] - cur["divCash"])
        alt *= (cur["close"] * cur["splitFactor"] + cur["divCash"]) / prev["close"]  # otra convención habitual
    assert total_return_adj == pytest.approx(manual, rel=1e-9)
    # Ambas convenciones de reinversión difieren muy poco (aquí < 0,1 % en 5 años); no hay doble conteo,
    # que daría un exceso del orden de la rentabilidad por dividendo (~2 % anual en este sintético).
    assert abs(total_return_adj / alt - 1) < 0.001

    from argos.data.sources import tiingo

    series = tiingo.parse_raw(text, "sintético")
    header = tiingo.render_converted(series).decode().splitlines()[0]
    assert header == "date,open,high,low,close,volume"  # sin divCash: imposible sumarlo otra vez
    import argos.backtest.engine as engine_mod
    assert "div" not in open(engine_mod.__file__, encoding="utf-8").read().lower().replace("divid", "")


# ----------------------------------------------------------------- costes, nulos y periodos


def test_costs_are_not_duplicated():
    df = ohlc([10, 10, 12, 12, 9, 9, 11, 11], [10, 10, 12, 12, 9, 9, 11, 11])
    sig = [Signal(date=df.index[i].date(), action=a, reason="t") for i, a in
           [(0, SignalAction.ENTER_LONG), (2, SignalAction.EXIT), (4, SignalAction.ENTER_LONG)]]
    res = Backtester().simulate(df, sig, BacktestConfig(initial_capital=1000, commission_pct=0.01, slippage_pct=0.02))
    assert len(res.trades) == 2  # la segunda se liquida al final
    assert res.total_commission == pytest.approx(sum(t.entry_commission + t.exit_commission for t in res.trades))
    assert res.total_slippage == pytest.approx(sum(t.slippage_cost for t in res.trades))
    assert res.final_equity == pytest.approx(1000 + sum(t.pnl for t in res.trades))
    gross = 1000 * (12 / 10) * (11 / 9)  # sin costes
    assert res.final_equity < gross


@pytest.mark.parametrize("col", ["open", "close"])
def test_engine_rejects_null_prices(col):
    df = ohlc([10.0] * 5, [10.0] * 5)
    df.loc[df.index[2], col] = float("nan")
    with pytest.raises(SimulationError, match="vacíos"):
        Backtester().simulate(df, [], BacktestConfig())


def test_reserved_holdout_data_does_not_change_results(tmp_path):
    """Si el CSV incluyera datos de 2026 (periodo reservado), los resultados de EXP-001 no cambian:
    la estrategia nunca ve datos posteriores al fin de cada periodo."""
    from argos.experiments.dryrun import write_demo_dataset
    from argos.experiments.protocol import load_protocol
    from argos.experiments.registry import ExperimentRegistry
    from argos.experiments.runner import run_experiment

    pdir = tmp_path / "p"
    pdir.mkdir()
    src = load_protocol("EXP-001")[2]
    shutil.copy(src, pdir / "EXP-001.json")
    shutil.copy(src.parent / "LOCKS.json", pdir / "LOCKS.json")
    protocol, _, _ = load_protocol("EXP-001", pdir)

    def dataset(folder, extend):
        folder.mkdir()
        mapping = write_demo_dataset(protocol, folder)
        for real, demo in mapping.items():  # nombres "reales" solo dentro del test (datos sintéticos)
            lines = (folder / f"{demo}.csv").read_text().splitlines()
            if extend:
                last = lines[-1].split(",")
                for d in pd.bdate_range("2026-01-02", "2026-03-31"):
                    lines.append(",".join([d.date().isoformat(), *last[1:]]))
            (folder / f"{real}.csv").write_text("\n".join(lines) + "\n")
            (folder / f"{demo}.csv").unlink()
            (folder / f"{demo}.source.txt").rename(folder / f"{real}.source.txt")
        return folder

    base = run_experiment("EXP-001", data_dir=dataset(tmp_path / "a", False),
                          registry=ExperimentRegistry(tmp_path / "ra.jsonl"), protocol_dir=pdir)
    ext = run_experiment("EXP-001", data_dir=dataset(tmp_path / "b", True),
                         registry=ExperimentRegistry(tmp_path / "rb.jsonl"), protocol_dir=pdir)
    key = lambda rs: [(r.ticker, r.period_name, r.end, r.strategy_return, r.benchmark_return, r.n_trades)  # noqa: E731
                      for r in rs]
    assert key(base.rows) == key(ext.rows)
    assert all(r.end <= "2025-12-31" for r in ext.rows)
