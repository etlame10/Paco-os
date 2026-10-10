import math

import pandas as pd
import pytest

from argos.analysis.technical import indicators as ind
from argos.analysis.technical.levels import support_resistance
from tests.conftest import make_df


def test_sma_known_values():
    s = pd.Series([1.0, 2, 3, 4, 5])
    out = ind.sma(s, 3)
    assert out.isna().sum() == 2
    assert list(out.dropna()) == [2.0, 3.0, 4.0]


def test_ema_converges_on_constant_series():
    assert ind.ema(pd.Series([10.0] * 50), 12).iloc[-1] == pytest.approx(10.0)


def test_rsi_extremes():
    up = pd.Series([float(i) for i in range(1, 40)])
    down = pd.Series([float(i) for i in range(40, 1, -1)])
    flat = pd.Series([5.0] * 40)
    assert ind.rsi(up).iloc[-1] == pytest.approx(100.0)
    assert ind.rsi(down).iloc[-1] == pytest.approx(0.0)
    assert ind.rsi(flat).iloc[-1] == pytest.approx(50.0)
    assert ind.rsi(up).iloc[:14].isna().all()  # sin datos suficientes -> vacío, no inventado


def test_rsi_bounded():
    s = pd.Series([100 + 5 * math.sin(i / 3) for i in range(200)])
    r = ind.rsi(s).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_macd_hist_is_difference():
    s = pd.Series([float(i) + math.sin(i) for i in range(100)])
    m = ind.macd(s).dropna()
    assert (m["hist"] - (m["macd"] - m["signal"])).abs().max() < 1e-9
    assert m["macd"].iloc[-1] > 0  # serie creciente -> EMA rápida por encima de la lenta


def test_atr_on_constant_range():
    df = make_df([100.0] * 40)
    assert ind.atr(df, 14).iloc[-1] == pytest.approx(2.0)


def test_drawdown_and_max_drawdown():
    s = pd.Series([100.0, 120, 90, 130, 117])
    assert ind.max_drawdown(s) == pytest.approx(-0.25)
    assert ind.drawdown(s).iloc[-1] == pytest.approx(-0.1)


def test_annualized_volatility_zero_for_geometric_growth():
    s = pd.Series([100 * 1.01**i for i in range(60)])
    assert ind.annualized_volatility(s, 20) == pytest.approx(0.0, abs=1e-9)
    assert ind.annualized_volatility(s.head(5), 20) is None  # datos insuficientes


def test_pct_change_over():
    s = pd.Series([100.0, 110, 121])
    assert ind.pct_change_over(s, 2) == pytest.approx(0.21)
    assert ind.pct_change_over(s, 5) is None


def test_support_resistance_brackets_price():
    closes = [100 + 10 * math.sin(i / 6) for i in range(200)]
    df = make_df(closes)
    lv = support_resistance(df)
    price = closes[-1]
    assert lv["support"] is None or lv["support"] < price
    assert lv["resistance"] is None or lv["resistance"] > price
    assert lv["support"] is not None or lv["resistance"] is not None
