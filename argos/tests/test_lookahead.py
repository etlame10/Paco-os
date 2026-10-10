"""Ausencia de look-ahead bias: indicadores, estrategia y auditoría automática."""

import math

import pandas as pd
import pytest

from argos.analysis.technical import indicators as ind
from argos.backtest.lookahead import LookAheadError, audit_lookahead
from argos.backtest.models import BacktestConfig
from argos.backtest.service import BacktestService
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry
from argos.strategy.base import Signal, SignalAction, Strategy
from argos.strategy.examples import SmaCrossover
from tests.conftest import make_df


@pytest.fixture(scope="module")
def demo_df():
    return DemoProvider().get_price_history("DEMO-VOLATIL").to_dataframe()


@pytest.mark.parametrize(
    "fn",
    [
        lambda df: ind.sma(df["close"], 20),
        lambda df: ind.sma(df["close"], 200),
        lambda df: ind.ema(df["close"], 12),
        lambda df: ind.rsi(df["close"], 14),
        lambda df: ind.macd(df["close"])["hist"],
        lambda df: ind.atr(df, 14),
    ],
    ids=["sma20", "sma200", "ema12", "rsi14", "macd_hist", "atr14"],
)
def test_indicators_do_not_use_future_data(demo_df, fn):
    """El valor en t debe ser idéntico tanto si existen datos posteriores a t como si no."""
    full = fn(demo_df)
    for cut in (210, 300, 450, len(demo_df) - 1):
        truncated = fn(demo_df.iloc[: cut + 1])
        pd.testing.assert_series_equal(full.iloc[: cut + 1], truncated, check_names=False)


def test_crossover_signals_on_hand_computed_series():
    # closes: 10 10 10 9 8 9 11 12 11 9 8  (SMA2 vs SMA3)
    # SMA2 > SMA3 por primera vez en la sesión 6 (10 > 9,33) → entrada
    # SMA2 < SMA3 en la sesión 9 (10 < 10,67) → salida
    df = make_df([10.0, 10, 10, 9, 8, 9, 11, 12, 11, 9, 8])
    sig = SmaCrossover(fast=2, slow=3).generate_signals(df)
    assert [(s.date, s.action) for s in sig] == [
        (df.index[6].date(), SignalAction.ENTER_LONG),
        (df.index[9].date(), SignalAction.EXIT),
    ]


def test_crossover_signal_only_uses_data_up_to_signal_day():
    df = make_df([10.0, 10, 10, 9, 8, 9, 11, 12, 11, 9, 8])
    # Cambiar todos los datos POSTERIORES a la sesión 6 no puede alterar la señal de la sesión 6.
    altered = df.copy()
    altered.iloc[7:, altered.columns.get_loc("close")] = 1000.0
    s1 = SmaCrossover(fast=2, slow=3).generate_signals(df)[0]
    s2 = SmaCrossover(fast=2, slow=3).generate_signals(altered)[0]
    assert s1 == s2


def test_audit_passes_for_honest_strategy(demo_df):
    audit = audit_lookahead(SmaCrossover(fast=20, slow=50), demo_df)
    assert audit.passed and audit.checked_cutoffs >= 8 and not audit.failures


class PeekingStrategy(Strategy):
    """Estrategia TRAMPOSA: compra hoy si mañana sube (usa el cierre futuro)."""

    name = "peeking"
    label = "Tramposa"
    description = "Mira el futuro (solo para tests)."

    @property
    def min_bars(self):
        return 2

    def generate_signals(self, df):
        tomorrow_up = df["close"].shift(-1) > df["close"]  # ← información futura
        out, long = [], False
        for ts, up in tomorrow_up.items():
            if up and not long:
                out.append(Signal(date=ts.date(), action=SignalAction.ENTER_LONG, reason="trampa"))
                long = True
            elif not up and long:
                out.append(Signal(date=ts.date(), action=SignalAction.EXIT, reason="trampa"))
                long = False
        return out


def test_audit_detects_strategy_that_peeks_into_future(demo_df):
    audit = audit_lookahead(PeekingStrategy(), demo_df)
    assert not audit.passed and audit.failures


def test_service_refuses_to_backtest_peeking_strategy():
    service = BacktestService(registry=ProviderRegistry([DemoProvider()]))
    with pytest.raises(LookAheadError):
        service.run_strategy("DEMO-LATERAL", PeekingStrategy(), BacktestConfig())


def test_peeking_would_look_great_which_is_why_it_must_be_blocked(demo_df):
    """Demuestra el peligro: con trampa, el resultado sería espectacular e irreal."""
    from argos.backtest.engine import Backtester

    sim = Backtester().simulate(demo_df, PeekingStrategy().generate_signals(demo_df),
                                BacktestConfig(commission_pct=0, slippage_pct=0))
    assert sim.final_equity > 10_000  # sin la auditoría, esto parecería una gran estrategia


def test_future_data_after_period_end_is_not_given_to_strategy():
    """Con un periodo que termina antes del final de los datos, la estrategia solo ve hasta `end`."""
    seen = {}

    class Recorder(SmaCrossover):
        def generate_signals(self, df):
            seen["last"] = max(seen.get("last", df.index[0]), df.index[-1])
            return super().generate_signals(df)

    service = BacktestService(registry=ProviderRegistry([DemoProvider()]))
    end = pd.Timestamp("2025-06-30")
    service.run_strategy("DEMO-LATERAL", Recorder(fast=10, slow=30), BacktestConfig(end=end.date()))
    assert seen["last"] <= end


def test_geometric_series_no_lookahead_sanity():
    closes = [100 * math.exp(0.01 * math.sin(i / 5)) for i in range(120)]
    audit = audit_lookahead(SmaCrossover(fast=5, slow=15), make_df(closes))
    assert audit.passed
