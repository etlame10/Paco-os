"""Motor de backtesting: casos sencillos con el resultado calculado A MANO.

Convención de los datos de prueba: ohlc(opens, closes) crea una sesión por
elemento. Las señales se dan por índice de sesión.
"""

from datetime import date

import pandas as pd
import pytest

from argos.backtest.engine import Backtester, SimulationError
from argos.backtest.metrics import compute_metrics
from argos.backtest.models import BacktestConfig
from argos.strategy.base import Signal, SignalAction

ENTER, EXIT = SignalAction.ENTER_LONG, SignalAction.EXIT


def ohlc(opens, closes):
    idx = pd.bdate_range("2024-01-01", periods=len(opens))
    return pd.DataFrame(
        {
            "open": opens,
            "high": [max(o, c) for o, c in zip(opens, closes)],
            "low": [min(o, c) for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [1000] * len(opens),
        },
        index=idx,
    )


def sig(df, i, action):
    return Signal(date=df.index[i].date(), action=action, reason="test")


def cfg(**kw):
    base = dict(initial_capital=1000.0, commission_pct=0.0, slippage_pct=0.0)
    base.update(kw)
    return BacktestConfig(**base)


# Datos base: la señal se calcula con el cierre de la sesión 0 (10) y se ejecuta a la
# apertura de la sesión 1 (10). Salida señalada en la sesión 2, ejecutada en la apertura de la 3 (12).
OPENS = [10.0, 10.0, 11.0, 12.0, 13.0]
CLOSES = [10.0, 10.5, 11.5, 12.5, 13.0]


def simulate(df, signals, **kw):
    return Backtester().simulate(df, signals, cfg(**kw))


# ----------------------------------------------------------------- compra y venta


def test_buy_and_sell_without_costs():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)])
    (t,) = res.trades
    # 1000 € / 10 € = 100 acciones; venta a 12 € = 1200 €.
    assert t.quantity == pytest.approx(100)
    assert t.entry_price == 10 and t.exit_price == 12
    assert t.pnl == pytest.approx(200)
    assert t.return_pct == pytest.approx(0.20)
    assert res.final_equity == pytest.approx(1200)
    assert t.entry_date == df.index[1].date() and t.exit_date == df.index[3].date()
    assert t.bars_held == 2
    assert t.exit_reason == "señal de salida"


def test_capital_curve_marked_to_market_each_day():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)])
    # sesión 0: liquidez 1000 · 1: 100×10,5 · 2: 100×11,5 · 3: vendido a 12 → 1200 · 4: 1200
    assert [p.equity for p in res.equity_curve] == pytest.approx([1000, 1050, 1150, 1200, 1200])
    assert [p.cash for p in res.equity_curve] == pytest.approx([1000, 0, 0, 1200, 1200])


def test_position_tracking():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)])
    assert [p.position_qty > 0 for p in res.equity_curve] == [False, True, True, False, False]
    assert compute_metrics(res).exposure == pytest.approx(2 / 5)


# ----------------------------------------------------------------- costes


def test_commission_applied_on_both_sides():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)], commission_pct=0.01)
    (t,) = res.trades
    qty = 1000 / (10 * 1.01)  # el efectivo cubre precio + comisión
    assert t.quantity == pytest.approx(qty)
    assert t.entry_commission == pytest.approx(qty * 10 * 0.01)
    assert t.exit_commission == pytest.approx(qty * 12 * 0.01)
    assert res.final_equity == pytest.approx(1000 * 12 / (10 * 1.01) * 0.99)  # = 1176,24
    assert res.final_equity == pytest.approx(1176.2376, abs=1e-3)
    assert res.total_commission == pytest.approx(t.entry_commission + t.exit_commission)


def test_slippage_moves_price_against_us():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)], slippage_pct=0.02)
    (t,) = res.trades
    assert t.entry_reference_price == 10 and t.entry_price == pytest.approx(10.2)
    assert t.exit_reference_price == 12 and t.exit_price == pytest.approx(11.76)
    assert res.final_equity == pytest.approx(1000 / 10.2 * 11.76)  # = 1152,94
    assert t.slippage_cost == pytest.approx(t.quantity * (0.2 + 0.24))


def test_commission_and_slippage_combined():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)], commission_pct=0.01, slippage_pct=0.02)
    expected = 1000 / (10 * 1.02 * 1.01) * (12 * 0.98) * 0.99
    assert res.final_equity == pytest.approx(expected)
    assert res.trades[0].pnl == pytest.approx(expected - 1000)


def test_costs_reduce_result_and_accounting_balances():
    df = ohlc(OPENS, CLOSES)
    signals = [sig(df, 0, ENTER), sig(df, 2, EXIT)]
    free = simulate(df, signals).final_equity
    costly = simulate(df, signals, commission_pct=0.005, slippage_pct=0.005)
    assert costly.final_equity < free
    # Contabilidad: capital final = inicial + suma de resultados de las operaciones.
    assert costly.final_equity == pytest.approx(1000 + sum(t.pnl for t in costly.trades))


# ----------------------------------------------------------------- ejecución temporal


def test_execution_uses_next_open_never_the_signal_day():
    # El cierre de la sesión de la señal (50) y la apertura siguiente (10) son muy distintos:
    # si el motor ejecutara con información del mismo día, el precio de entrada sería 50.
    df = ohlc([10, 10, 20, 20], [50, 15, 20, 20])
    res = simulate(df, [sig(df, 0, ENTER)], liquidate_at_end=False)
    (point0, point1, *_rest) = res.equity_curve
    assert point0.position_qty == 0  # el día de la señal sigue en liquidez
    assert point1.position_qty == pytest.approx(100)  # compró a la apertura siguiente (10)
    assert res.trades == []  # sin liquidar: la operación sigue abierta
    assert res.final_equity == pytest.approx(100 * 20)


def test_trade_dates_always_after_signal_dates():
    df = ohlc(OPENS * 4, CLOSES * 4)
    signals = [sig(df, i, ENTER if k % 2 == 0 else EXIT) for k, i in enumerate([0, 3, 6, 9, 12, 15])]
    res = simulate(df, signals)
    assert res.trades
    for t in res.trades:
        assert t.entry_signal_date < t.entry_date
        assert t.exit_signal_date is None or t.exit_signal_date < t.exit_date


def test_signal_on_last_bar_is_not_executed():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 4, ENTER)])
    assert res.trades == [] and res.final_equity == 1000
    assert "última sesión" in res.ignored_signals[0].reason


def test_redundant_signals_are_ignored_and_reported():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, EXIT), sig(df, 1, ENTER), sig(df, 2, ENTER)])
    reasons = [i.reason for i in res.ignored_signals]
    assert reasons == ["No había posición que cerrar.", "Ya había una posición abierta."]
    assert len(res.trades) == 1  # la posición abierta se liquida al final


def test_liquidation_at_end_uses_last_close_with_costs():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [sig(df, 0, ENTER)], commission_pct=0.01, slippage_pct=0.01)
    (t,) = res.trades
    assert t.exit_reason == "liquidación al final del periodo"
    assert t.exit_reference_price == 13.0 and t.exit_price == pytest.approx(13 * 0.99)
    expected = 1000 / (10 * 1.01 * 1.01) * 13 * 0.99 * 0.99
    assert res.final_equity == pytest.approx(expected)
    assert res.equity_curve[-1].equity == pytest.approx(expected)


def test_multiple_round_trips_compound():
    df = ohlc([10, 10, 20, 20, 10, 10, 10], [10, 10, 20, 20, 10, 10, 10])
    # Compra a 10 (s1) → vende a 20 (s3) → compra a 10 (s5) → liquida a 10 (s6).
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT), sig(df, 4, ENTER)])
    assert [round(t.return_pct, 6) for t in res.trades] == [1.0, 0.0]
    assert res.final_equity == pytest.approx(2000)


# ----------------------------------------------------------------- métricas


def test_drawdown_from_equity_curve():
    # Comprado todo el tiempo: capital = 100 × cierre → 1000, 1200, 900, 1300, 1170
    df = ohlc([10, 10, 10, 10, 10, 10], [10, 10, 12, 9, 13, 11.7])
    res = simulate(df, [sig(df, 0, ENTER)], liquidate_at_end=False)
    m = compute_metrics(res)
    assert m.max_drawdown == pytest.approx(900 / 1200 - 1)  # −25%
    assert m.total_return == pytest.approx(0.17)


def test_trade_statistics():
    df = ohlc([10, 10, 20, 20, 10, 10, 5, 5], [10] * 8)
    # +100% (10→20), luego −50% (10→5)
    res = simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT), sig(df, 4, ENTER), sig(df, 6, EXIT)])
    m = compute_metrics(res)
    assert m.n_trades == 2
    assert m.win_rate == 0.5
    assert m.best_trade_return == pytest.approx(1.0)
    assert m.worst_trade_return == pytest.approx(-0.5)
    assert m.avg_trade_return == pytest.approx(0.25)
    assert m.avg_trade_pnl == pytest.approx((1000 + -1000) / 2)  # +1000 y luego −1000 (2000 → 1000)


def test_sharpe_and_annualization_need_enough_data():
    df = ohlc(OPENS, CLOSES)
    m = compute_metrics(simulate(df, [sig(df, 0, ENTER)]))
    assert m.sharpe is None and "60" in m.sharpe_note
    assert m.volatility is None
    assert m.annualized_return is None and m.annualized_return_note


def test_no_signals_means_flat_cash():
    df = ohlc(OPENS, CLOSES)
    res = simulate(df, [])
    m = compute_metrics(res)
    assert res.final_equity == 1000 and m.n_trades == 0 and m.win_rate is None
    assert m.max_drawdown == 0 and m.exposure == 0


# ----------------------------------------------------------------- entradas inválidas


def test_engine_rejects_bad_inputs():
    df = ohlc(OPENS, CLOSES)
    with pytest.raises(SimulationError):
        Backtester().simulate(df.iloc[0:0], [], cfg())  # sin datos
    with pytest.raises(SimulationError):
        Backtester().simulate(df, [Signal(date=date(2030, 1, 1), action=ENTER, reason="x")], cfg())
    with pytest.raises(SimulationError):
        Backtester().simulate(df, [sig(df, 1, ENTER), sig(df, 1, EXIT)], cfg())
    with pytest.raises(SimulationError):
        Backtester().simulate(df.iloc[::-1], [], cfg())  # fechas desordenadas


def test_config_validation():
    with pytest.raises(ValueError):
        BacktestConfig(initial_capital=0)
    with pytest.raises(ValueError):
        BacktestConfig(commission_pct=-0.01)
    with pytest.raises(ValueError):
        BacktestConfig(slippage_pct=0.5)
    with pytest.raises(ValueError):
        BacktestConfig(start=date(2025, 1, 1), end=date(2024, 1, 1))


def test_engine_is_strategy_agnostic(root):
    """El motor no importa ni conoce ninguna estrategia concreta."""
    src = (root / "argos" / "backtest" / "engine.py").read_text(encoding="utf-8")
    assert "examples" not in src and "SmaCrossover" not in src and "BuyAndHold" not in src
    assert "generate_signals" not in src


def test_volatility_sharpe_and_cagr_hand_computed():
    import math

    import numpy as np

    from argos.backtest import metrics as mt

    # Rendimientos diarios alternos +2% / −1% durante 100 sesiones.
    rets = np.array([0.02, -0.01] * 50)
    equity = pd.Series(1000 * np.cumprod(np.concatenate([[1.0], 1 + rets])),
                       index=pd.bdate_range("2024-01-01", periods=101))
    sd = rets.std(ddof=1)
    assert mt.volatility(equity) == pytest.approx(sd * math.sqrt(252))
    assert mt.sharpe(equity) == pytest.approx(rets.mean() / sd * math.sqrt(252))
    assert mt.sharpe(equity, risk_free=0.0252) == pytest.approx((rets.mean() - 0.0001) / sd * math.sqrt(252))
    # CAGR: duplicar en exactamente 2 años naturales (731 días) → ≈ 41,4% anual.
    two_years = pd.Series([100.0, 200.0], index=pd.to_datetime(["2022-01-01", "2024-01-02"]))
    assert mt.annualized_return(two_years) == pytest.approx(2 ** (365.25 / 731) - 1)
