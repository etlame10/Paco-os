"""TESTS UNITARIOS del motor de carteras de EXP-002 (argos/backtest/portfolio.py).

Precios INVENTADOS y pequeños, con resultados calculados a mano. No dicen nada sobre ninguna estrategia.
"""

import math
from datetime import date

import numpy as np
import pytest

from argos.backtest.portfolio import (
    CostModel,
    Execution,
    InsufficientCashError,
    Market,
    PortfolioError,
    PriceDataError,
    cagr,
    calendar_year_returns,
    excess_returns,
    max_drawdown,
    monthly_returns,
    sharpe_excess,
    simulate,
    sortino_excess,
    volatility,
)

D = (date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4))


def mk(opens, closes, days=D):
    return Market(tuple(days), {k: np.array(v, float) for k, v in opens.items()},
                  {k: np.array(v, float) for k, v in closes.items()})


@pytest.fixture
def two_assets():
    return mk({"A": [10, 11, 12], "B": [20, 20, 25]}, {"A": [10, 11, 12], "B": [20, 22, 25]})


def test_hand_calculated_switch_and_final_liquidation(two_assets):
    m, s, C0 = 1.0, 0.01, 100.0
    run = simulate(two_assets, [Execution(0, {"A": 1}, reason="entrada"), Execution(1, {"B": 1})],
                   CostModel(m, s), C0, 0, 2)
    qa = (C0 - m) / (10 * (1 + s))                      # compra de A en la apertura de la sesión 0
    cash1 = qa * 11 * (1 - s) - m                        # venta de A en la apertura de la sesión 1
    qb = (cash1 - m) / (20 * (1 + s))                    # compra de B en esa misma apertura
    final = qb * 25 * (1 - s) - m                        # liquidación al CIERRE de la última sesión
    assert run.values == pytest.approx([C0, qa * 10, qb * 22, final], rel=1e-12)
    assert [(o.date, o.ticker, o.side, o.kind, o.timing) for o in run.orders] == [
        (D[0], "A", "compra", "entrada", "open"), (D[1], "A", "venta", "cambio", "open"),
        (D[1], "B", "compra", "cambio", "open"), (D[2], "B", "venta", "liquidación", "close")]
    assert [o.commission for o in run.orders] == [m] * 4
    assert [o.slippage_cost for o in run.orders] == pytest.approx([qa * 10 * s, qa * 11 * s, qb * 20 * s, qb * 25 * s])
    assert run.orders[0].execution_price == pytest.approx(10 * 1.01) and run.orders[3].execution_price == pytest.approx(25 * 0.99)
    assert run.switches == 1 and run.commissions == 4 * m
    assert run.gross_market_result == pytest.approx(qa * (11 - 10) + qb * (25 - 20))
    assert abs(run.accounting_identity_gap()) < 1e-9
    assert run.holdings == [frozenset("A"), frozenset("B"), frozenset("B")]


def test_same_target_generates_no_orders(two_assets):
    run = simulate(two_assets, [Execution(0, {"A": 1}), Execution(1, {"A": 1}), Execution(2, {"A": 1})],
                   CostModel(1.0, 0.0005), 100, 0, 2)
    assert len(run.orders) == 2 and run.switches == 0  # entrada + liquidación


def test_order_counts_match_protocol_formulas():
    rng = np.random.default_rng(5)
    n = 40
    days = [date.fromordinal(date(2024, 1, 1).toordinal() + i) for i in range(n)]
    px = {t: 50 * np.cumprod(1 + rng.normal(0, 0.01, n)) for t in "ABC"}
    mkt = Market(tuple(days), {t: v * 1.001 for t, v in px.items()}, px)
    cm = CostModel(1.0, 0.0005)
    gem = simulate(mkt, [Execution(0, {"A": 1}), Execution(10, {"B": 1}), Execution(20, {"B": 1}),
                         Execution(25, {"C": 1}), Execution(30, {"A": 1})], cm, 100, 0, n - 1)
    k = gem.switches
    assert k == 3 and len(gem.orders) == 2 + 2 * k
    bh = simulate(mkt, [Execution(0, {"A": 1})], cm, 100, 0, n - 1)
    mix = simulate(mkt, [Execution(0, {"A": 0.3, "B": 0.3, "C": 0.4})], cm, 100, 0, n - 1)
    assert len(bh.orders) == 2 and len(mix.orders) == 6
    for run in (gem, bh, mix):
        assert run.commissions == len(run.orders) * 1.0
        assert abs(run.accounting_identity_gap()) < 1e-9


def test_buy_and_hold_mix_has_no_rebalancing_and_weights_drift():
    mkt = mk({"A": [10, 10, 10], "B": [10, 10, 10], "C": [10, 10, 10]},
             {"A": [10, 20, 20], "B": [10, 10, 10], "C": [10, 5, 5]})
    run = simulate(mkt, [Execution(0, {"A": 0.3, "B": 0.3, "C": 0.4})], CostModel(1.0, 0.0), 100, 0, 2)
    budget = 100 - 3
    q = {"A": 0.3 * budget / 10, "B": 0.3 * budget / 10, "C": 0.4 * budget / 10}
    assert [o.side for o in run.orders] == ["compra"] * 3 + ["venta"] * 3  # sin órdenes intermedias
    assert run.values[2] == pytest.approx(q["A"] * 20 + q["B"] * 10 + q["C"] * 5)  # cantidades fijas, pesos libres
    assert run.final_value == pytest.approx(q["A"] * 20 + q["B"] * 10 + q["C"] * 5 - 3)


def test_dividends_are_reinvested_through_adjusted_prices():
    """Precio sin ajustar 100 → 99 por un dividendo de 1 en la fecha ex. Ajuste hacia atrás: antes × (1 − 1/100).
    Con precios ajustados el valor de comprar y mantener queda plano: el dividendo se reinvierte sin comisión."""
    raw_close = np.array([100.0, 100.0, 99.0, 99.0])
    factor = np.array([0.99, 0.99, 1.0, 1.0])
    adj = raw_close * factor
    days = (date(2024, 3, 1), date(2024, 3, 4), date(2024, 3, 5), date(2024, 3, 6))
    mkt = Market(days, {"X": adj}, {"X": adj})
    run = simulate(mkt, [Execution(0, {"X": 1})], CostModel(0.0, 0.0), 100, 0, 3)
    assert run.values == pytest.approx([100, 100, 100, 100, 100])
    total_return = (raw_close[-1] + 1.0) / raw_close[0] - 1  # precio final + dividendo cobrado
    assert run.final_value / 100 - 1 == pytest.approx(total_return)


def test_close_timing_uses_close_price(two_assets):
    run = simulate(two_assets, [Execution(0, {"A": 1}), Execution(1, {"B": 1}, timing="close")],
                   CostModel(0.0, 0.0), 100, 0, 2)
    sell = [o for o in run.orders if o.side == "venta"][0]
    buy_b = [o for o in run.orders if o.ticker == "B"][0]
    assert (sell.date, sell.reference_price, sell.timing) == (D[1], 11.0, "close")
    assert (buy_b.reference_price, buy_b.timing) == (22.0, "close")
    assert run.values[2] == pytest.approx(10 * 11)  # 10 participaciones de A vendidas a 11 → todo en B a 22


def test_insufficient_cash_stops_instead_of_forcing(two_assets):
    with pytest.raises(InsufficientCashError, match="prohíbe forzar"):
        simulate(two_assets, [Execution(0, {"A": 1})], CostModel(1.0, 0.0), 1.0, 0, 2)
    with pytest.raises(InsufficientCashError):  # 2 compras de comisión 1 con 1,5 de capital
        simulate(two_assets, [Execution(0, {"A": 0.5, "B": 0.5})], CostModel(1.0, 0.0), 1.5, 0, 2)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_prices_are_rejected(bad):
    with pytest.raises(PriceDataError, match="no válido"):
        mk({"A": [10, bad, 12]}, {"A": [10, 11, 12]})
    with pytest.raises(PriceDataError, match="no válido"):
        mk({"A": [10, 11, 12]}, {"A": [10, 11, bad]})


def test_market_structure_errors():
    with pytest.raises(PriceDataError, match="ninguna sesión"):
        Market((), {}, {})
    with pytest.raises(PriceDataError, match="creciente"):
        mk({"A": [1, 1, 1]}, {"A": [1, 1, 1]}, days=(D[1], D[0], D[2]))
    with pytest.raises(PriceDataError, match="precios de"):
        mk({"A": [1, 1]}, {"A": [1, 1, 1]})


def test_execution_validation(two_assets):
    cm = CostModel(1.0, 0.0)
    with pytest.raises(PortfolioError, match="fuera del tramo"):
        simulate(two_assets, [Execution(2, {"A": 1})], cm, 100, 0, 1)
    with pytest.raises(PortfolioError, match="misma sesión"):
        simulate(two_assets, [Execution(0, {"A": 1}), Execution(0, {"B": 1})], cm, 100, 0, 2)
    with pytest.raises(PortfolioError, match="sumar 1"):
        simulate(two_assets, [Execution(0, {"A": 0.5})], cm, 100, 0, 2)
    with pytest.raises(PortfolioError, match="sin precios"):
        simulate(two_assets, [Execution(0, {"Z": 1})], cm, 100, 0, 2)


def test_percentage_commission_formula():
    cm = CostModel(1.0, 0.0, commission_pct=0.01)
    assert cm.buy_commission(50) == 1.0  # 1% de 50/1,01 < 1 → mínimo
    c = cm.buy_commission(1000)
    assert c == pytest.approx(0.01 * (1000 - c))  # c = p × (A − c)
    assert cm.sell_commission(500) == 5.0


# ------------------------------------------------------------------ métricas


def test_max_drawdown_includes_initial_point_and_all_sessions():
    assert max_drawdown([100, 120, 90, 130, 117]) == pytest.approx(1 - 90 / 120)
    assert max_drawdown([100, 99, 98]) == pytest.approx(0.02)  # el coste de entrada ya es caída desde V_0
    assert max_drawdown([100, 110, 120]) == 0.0


def test_cagr_uses_calendar_days():
    assert cagr(100, 121, date(2020, 1, 1), date(2022, 1, 1)) == pytest.approx(1.21 ** (365.25 / 731) - 1)
    assert cagr(100, 100, date(2020, 1, 1), date(2020, 1, 1)) is None
    assert cagr(100, -1, date(2020, 1, 1), date(2021, 1, 1)) is None


def test_excess_sharpe_sortino_and_volatility_definitions():
    v = [100, 101, 100.5, 102, 101, 103]
    bil = np.array([10, 10.001, 10.002, 10.003, 10.004, 10.005])
    e = excess_returns(v, bil)
    r = np.array(v[1:]) / np.array(v[:-1]) - 1
    rb = bil[1:] / bil[:-1] - 1
    assert e == pytest.approx(r - rb)
    assert sharpe_excess(e) == pytest.approx(np.mean(e) / np.std(e, ddof=1) * math.sqrt(252))
    assert sortino_excess(e) == pytest.approx(np.mean(e) / math.sqrt(np.mean(np.minimum(e, 0) ** 2)) * math.sqrt(252))
    assert volatility(v) == pytest.approx(np.std(r, ddof=1) * math.sqrt(252))
    with pytest.raises(PortfolioError):
        excess_returns(v, bil[1:])


def test_calendar_years_and_months():
    dates = [date(2019, 12, 31), date(2020, 1, 31), date(2020, 12, 31), date(2021, 6, 30)]
    values = [100, 110, 120, 132, 99]
    years = calendar_year_returns(dates, values)
    assert years[2019] == (pytest.approx(0.10), False)  # el tramo empieza el 31-dic: año incompleto
    assert years[2020] == (pytest.approx(0.2), True)
    assert years[2021] == (pytest.approx(99 / 132 - 1), False)
    assert monthly_returns(dates, values) == pytest.approx([0.10, 120 / 110 - 1, 132 / 120 - 1, 99 / 132 - 1])
