"""TESTS UNITARIOS de la estrategia GEM (argos/strategy/gem.py) con precios INVENTADOS.

Comprueban la regla, las fechas de decisión y que no se usa información futura. No evalúan la estrategia.
"""

from datetime import date

import numpy as np
import pytest

from argos.backtest.portfolio import Market
from argos.data.calendar_us import sessions
from argos.strategy.gem import gem_decisions, gem_target, nyse_month_end, shift_month

TICKERS = ("SPY", "VEU", "AGG", "BIL")


def synthetic_market(start=date(2018, 1, 2), end=date(2021, 12, 31), seed=3):
    days = sessions(start, end)
    rng = np.random.default_rng(seed)
    closes = {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(days))) for t in TICKERS}
    opens = {t: c * (1 + rng.normal(0, 0.002, len(days))) for t, c in closes.items()}
    return Market(tuple(days), opens, closes)


@pytest.mark.parametrize("spy, veu, bil, principal, s1", [
    (0.10, 0.05, 0.01, "SPY", "SPY"),
    (0.05, 0.10, 0.01, "VEU", "VEU"),
    (0.00, -0.05, 0.01, "AGG", "AGG"),
    (0.00, 0.05, 0.01, "AGG", "VEU"),   # único caso en que difieren: SPY bajo las letras, VEU por encima
    (0.01, 0.00, 0.01, "AGG", "AGG"),   # empate R_SPY = R_BIL → "no supera" → AGG
    (0.05, 0.05, 0.01, "SPY", "SPY"),   # empate R_SPY = R_VEU → SPY
    (-0.02, -0.01, -0.03, "VEU", "VEU"),  # letras negativas: SPY > BIL, VEU mejor
])
def test_rule_truth_table(spy, veu, bil, principal, s1):
    assert gem_target(spy, veu, bil, "principal") == principal
    assert gem_target(spy, veu, bil, "S1") == s1


def test_month_end_dates_come_from_nyse_calendar():
    assert nyse_month_end(2014, 12) == date(2014, 12, 31)
    assert nyse_month_end(2025, 11) == date(2025, 11, 28)  # viernes tras Acción de Gracias
    assert nyse_month_end(2026, 9) == date(2026, 9, 30)
    assert nyse_month_end(2018, 3) == date(2018, 3, 29)    # 30-mar-2018 fue Viernes Santo
    assert shift_month(2015, 1, 12) == (2014, 1) and shift_month(2015, 3, 6) == (2014, 9)


@pytest.mark.parametrize("lookback", [6, 9, 12])
def test_momentum_is_computed_from_adjusted_closes_at_month_ends(lookback):
    mkt = synthetic_market()
    decs = gem_decisions(mkt, lookback)
    first = decs[0]
    assert first.reference_date == nyse_month_end(*shift_month(first.date.year, first.date.month, lookback))
    assert first.reference_date >= mkt.sessions[0]  # nunca antes de tener datos
    pos = {d: i for i, d in enumerate(mkt.sessions)}
    for d in decs:
        i, j = pos[d.date], pos[d.reference_date]
        assert d.index == i and d.date == nyse_month_end(d.date.year, d.date.month)
        for t, r in (("SPY", d.r_spy), ("VEU", d.r_veu), ("BIL", d.r_bil)):
            assert r == mkt.closes[t][i] / mkt.closes[t][j] - 1
        assert d.target == gem_target(d.r_spy, d.r_veu, d.r_bil)
    # Una decisión por mes desde el primer mes con historia suficiente.
    assert len(decs) == len({(d.year, d.month) for d in mkt.sessions}) - lookback


def test_no_future_information_by_truncation():
    mkt = synthetic_market()
    full = gem_decisions(mkt)
    for d in full:
        assert gem_decisions(mkt.truncated(d.index))[-1] == d


def test_changing_future_prices_does_not_change_past_decisions():
    mkt = synthetic_market()
    full = gem_decisions(mkt)
    d = full[len(full) // 2]
    altered = {t: c.copy() for t, c in mkt.closes.items()}
    altered["SPY"][d.index + 1:] *= 0.1  # todo lo posterior al cierre de decisión cambia
    altered["VEU"][d.index + 1:] *= 10
    other = Market(mkt.sessions, mkt.opens, altered)
    assert [x for x in gem_decisions(other) if x.date <= d.date] == [x for x in full if x.date <= d.date]
    # Las aperturas nunca intervienen en la señal.
    opens = {t: o * 3 for t, o in mkt.opens.items()}
    assert gem_decisions(Market(mkt.sessions, opens, mkt.closes)) == full


def test_close_of_decision_day_does_matter():
    mkt = synthetic_market()
    d = gem_decisions(mkt)[-5]
    altered = {t: c.copy() for t, c in mkt.closes.items()}
    altered["BIL"][d.index] *= 2  # BIL +100% en 12 meses → SPY no supera a las letras
    new = [x for x in gem_decisions(Market(mkt.sessions, mkt.opens, altered)) if x.date == d.date][0]
    assert new.target == "AGG"


def test_incomplete_last_month_is_not_a_decision():
    mkt = synthetic_market(end=date(2021, 12, 15))
    assert gem_decisions(mkt)[-1].date == date(2021, 11, 30)


def test_missing_asset_is_an_error():
    mkt = synthetic_market()
    closes = {t: v for t, v in mkt.closes.items() if t != "BIL"}
    opens = {t: v for t, v in mkt.opens.items() if t != "BIL"}
    with pytest.raises(ValueError, match="BIL"):
        gem_decisions(Market(mkt.sessions, opens, closes))
