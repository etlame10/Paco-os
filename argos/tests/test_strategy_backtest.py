import math
import pandas as pd
import pytest

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
    full = SmaCrossover(fast=10, slow=30).generate_signals(df)
    cut = df.index[250]
    partial = SmaCrossover(fast=10, slow=30).generate_signals(df.loc[:cut])
    assert partial == [s for s in full if s.date <= cut.date()]


def test_sma_crossover_validates_params():
    with pytest.raises(ValueError):
        SmaCrossover(fast=50, slow=20)
