import math
from datetime import date

import pandas as pd
import pytest

from argos.backtest import metrics as m
from argos.backtest.engine import BacktestEngine
from argos.backtest.models import BacktestConfig, BacktestMetrics, BacktestResult, Trade
from argos.strategy.base import SignalAction, available_strategies, get_strategy
from argos.strategy.examples import BuyAndHold, SmaCrossover
from tests.conftest import make_df


def test_strategies_registered():
    names = available_strategies()
    assert "buy_and_hold" in names and "sma_crossover" in names


def test_buy_and_hold_single_entry():
    sig = BuyAndHold().generate_signals(make_df([1.0, 2, 3]))
    assert len(sig) == 1 and sig[0].action is SignalAction.ENTER_LONG and sig[0].hypothetical


def test_sma_crossover_alternates_and_is_hypothetical():
    closes = [100 + 20 * math.sin(i / 25) for i in range(400)]
    sig = get_strategy("sma_crossover", fast=10, slow=30).generate_signals(make_df(closes))
    assert len(sig) >= 2
    assert all(s.hypothetical for s in sig)
    actions = [s.action for s in sig]
    assert all(a != b for a, b in zip(actions, actions[1:]))


def test_sma_crossover_uses_no_future_data():
    closes = [100 + 20 * math.sin(i / 25) for i in range(400)]
    df = make_df(closes)
    full = SmaCrossover(10, 30).generate_signals(df)
    cut = df.index[250]
    partial = SmaCrossover(10, 30).generate_signals(df.loc[:cut])
    assert partial == [s for s in full if s.date <= cut.date()]


def test_sma_crossover_validates_params():
    with pytest.raises(ValueError):
        SmaCrossover(fast=50, slow=20)


def test_backtest_metrics():
    equity = pd.Series([100.0, 110, 99, 121])
    assert m.total_return(equity) == pytest.approx(0.21)
    assert m.annualized_return(pd.Series([100.0] * 252 + [110.0])) == pytest.approx(0.10)
    t1 = Trade(entry_date=date(2024, 1, 1), entry_price=10, exit_date=date(2024, 2, 1), exit_price=12, quantity=1)
    t2 = Trade(entry_date=date(2024, 3, 1), entry_price=10, exit_date=date(2024, 4, 1), exit_price=9, quantity=1)
    t3 = Trade(entry_date=date(2024, 5, 1), entry_price=10, quantity=1)  # abierta
    assert m.win_rate([t1, t2, t3]) == 0.5
    assert m.win_rate([]) is None
    res = m.compute_metrics(equity, [t1, t2])
    assert res.max_drawdown == pytest.approx(-0.1)
    assert res.n_trades == 2
    assert res.profit_loss == pytest.approx(21.0)


def test_backtest_engine_contract_compares_against_buy_and_hold():
    seen = []

    class FakeEngine(BacktestEngine):
        def run(self, strategy, history, config):
            seen.append(strategy.name)
            return BacktestResult(
                strategy=strategy.name, params=strategy.params, ticker=history.ticker, config=config,
                metrics=BacktestMetrics(total_return=0, annualized_return=None, max_drawdown=0, volatility=None,
                                        sharpe=None, n_trades=0, win_rate=None, profit_loss=0),
                is_simulated_data=history.provenance.is_simulated,
            )

    from argos.data.providers.demo import DemoProvider

    hist = DemoProvider().get_price_history("DEMO-LATERAL")
    out = FakeEngine().compare([SmaCrossover()], hist, BacktestConfig())
    assert seen == ["buy_and_hold", "sma_crossover"]
    assert all(r.is_simulated_data for r in out)
