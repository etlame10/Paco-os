"""Backtest completo: datos → estrategia → señales → motor → comparación con Buy & Hold."""

from datetime import date

import pytest

from argos.backtest.comparison import compare
from argos.backtest.metrics import compute_metrics
from argos.backtest.models import BacktestConfig
from argos.backtest.service import BacktestService, InsufficientDataError
from argos.data.providers.csv_provider import CsvProvider
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry
from argos.strategy.base import get_strategy


@pytest.fixture(scope="module")
def service():
    return BacktestService(registry=ProviderRegistry([DemoProvider()]))


@pytest.fixture(scope="module")
def report(service):
    return service.run("DEMO-LATERAL", "sma_crossover", {}, BacktestConfig(commission_pct=0.001, slippage_pct=0.0005))


def test_buy_and_hold_matches_independent_calculation(service):
    """B&H recalculado sin usar el motor: compra a la apertura de la 2.ª sesión, vende al último cierre."""
    cfg = BacktestConfig(initial_capital=10_000, commission_pct=0.002, slippage_pct=0.001)
    for ticker in DemoProvider().list_tickers():
        rep = service.run(ticker, "sma_crossover", {}, cfg)
        bars = DemoProvider().get_price_history(ticker).bars
        c, s = cfg.commission_pct, cfg.slippage_pct
        qty = cfg.initial_capital / (bars[1].open * (1 + s) * (1 + c))
        final = qty * bars[-1].close * (1 - s) * (1 - c)
        assert rep.benchmark.metrics.final_capital == pytest.approx(final, rel=1e-12)
        assert rep.benchmark.metrics.total_return == pytest.approx(final / 10_000 - 1, rel=1e-9)
        assert rep.benchmark.metrics.n_trades == 1


def test_report_is_transparent(report):
    tr = report.transparency
    assert tr.data["is_simulated"] is True and tr.data["frequency"] == "diaria"
    assert tr.strategy["name"] == "sma_crossover" and tr.strategy["params"] == {"fast": 50, "slow": 200}
    assert "0.100%" in tr.commission and "0.050%" in tr.slippage
    assert tr.period["start"] and tr.period["end"]
    assert "t+1" in tr.execution_rule
    assert "NO PREDICCIÓN" in report.warning and "no garantizan" in report.warning
    assert report.kind == "resultado_historico"
    assert report.live_trading_enabled is False


def test_report_consistency(report):
    sim, m = report.strategy.simulation, report.strategy.metrics
    assert m.final_capital == pytest.approx(sim.final_equity)
    assert m.final_capital == pytest.approx(m.initial_capital + sum(t.pnl for t in sim.trades))
    assert report.lookahead_audit.passed
    assert [p.date for p in sim.equity_curve] == [p.date for p in report.benchmark.simulation.equity_curve]
    assert all(s.hypothetical for s in report.strategy.signals)


def test_comparison_contains_required_items(report):
    metrics = [i.metric for i in report.comparison.items]
    assert metrics == ["total_return", "max_drawdown", "volatility", "sharpe"]
    tr = next(i for i in report.comparison.items if i.metric == "total_return")
    assert tr.difference == pytest.approx(report.strategy.metrics.total_return - report.benchmark.metrics.total_return)
    assert any("SIMULADOS" in c for c in report.comparison.caveats)
    assert any("base estadística" in c for c in report.comparison.caveats)


def test_making_money_is_not_enough_to_be_good(service):
    """Si la estrategia gana pero menos que B&H, el veredicto NO puede ser positivo."""
    rep = service.run("DEMO-VOLATIL", "sma_crossover", {}, BacktestConfig())
    assert rep.strategy.metrics.total_return > 0
    assert rep.strategy.metrics.total_return < rep.benchmark.metrics.total_return
    assert "más rentabilidad" not in rep.comparison.verdict
    assert any("no significa que sea buena" in c for c in rep.comparison.caveats)


def test_zero_trades_verdict(service):
    rep = service.run("DEMO-ALCISTA", "sma_crossover", {}, BacktestConfig())
    assert rep.strategy.metrics.n_trades == 0
    assert "no llegó a operar" in rep.comparison.verdict


def test_compare_marks_better_and_worse():
    from argos.backtest.engine import Backtester
    from tests.test_backtest_engine import CLOSES, OPENS, ohlc, sig, ENTER, EXIT

    df = ohlc(OPENS, CLOSES)
    a = compute_metrics(Backtester().simulate(df, [sig(df, 0, ENTER), sig(df, 2, EXIT)], BacktestConfig(commission_pct=0, slippage_pct=0)))
    b = compute_metrics(Backtester().simulate(df, [sig(df, 0, ENTER)], BacktestConfig(commission_pct=0, slippage_pct=0)))
    c = compare(a, b, simulated_data=False)
    tr = c.items[0]
    assert tr.strategy == pytest.approx(0.20) and tr.benchmark == pytest.approx(0.30)
    assert tr.better is False and tr.difference == pytest.approx(-0.10)


# ----------------------------------------------------------------- periodos y datos insuficientes


def test_period_selection_and_warmup_uses_prior_history(service):
    rep = service.run("DEMO-VOLATIL", "sma_crossover", {"fast": 20, "slow": 50},
                      BacktestConfig(start=date(2025, 1, 1), end=date(2025, 12, 31)))
    assert rep.transparency.period["start"] >= "2025-01-01"
    assert rep.transparency.period["end"] <= "2025-12-31"
    # Hay historia previa suficiente, así que no aparece la nota de calentamiento.
    assert not any("no puede emitir señales" in n for n in rep.notes)
    assert rep.benchmark.simulation.equity_curve[0].date >= date(2025, 1, 1)


def test_period_outside_data(service):
    with pytest.raises(InsufficientDataError):
        service.run("DEMO-LATERAL", "sma_crossover", {}, BacktestConfig(start=date(2010, 1, 1), end=date(2010, 12, 31)))


def test_period_too_short(service):
    with pytest.raises(InsufficientDataError):
        service.run("DEMO-LATERAL", "sma_crossover", {}, BacktestConfig(start=date(2025, 12, 20)))


def test_insufficient_history_for_strategy(tmp_path):
    lines = ["date,open,high,low,close,volume"]
    bars = DemoProvider().get_price_history("DEMO-LATERAL").bars[:150]
    lines += [f"{b.date},{b.open},{b.high},{b.low},{b.close},{b.volume}" for b in bars]
    (tmp_path / "CORTO.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    svc = BacktestService(registry=ProviderRegistry([CsvProvider(tmp_path)]))
    with pytest.raises(InsufficientDataError, match="necesita 201 sesiones"):
        svc.run("CORTO", "sma_crossover", {}, BacktestConfig())
    # Con medias más cortas sí hay datos suficientes.
    assert svc.run("CORTO", "sma_crossover", {"fast": 10, "slow": 30}, BacktestConfig()).is_simulated_data is False


def test_strategy_parameter_validation():
    with pytest.raises(ValueError):
        get_strategy("sma_crossover", fast=200, slow=50)
    with pytest.raises(ValueError):
        get_strategy("sma_crossover", fast=1)
    with pytest.raises(ValueError):
        get_strategy("sma_crossover", fast="diez")
    with pytest.raises(ValueError):
        get_strategy("sma_crossover", fast=10.5)
    with pytest.raises(ValueError):
        get_strategy("sma_crossover", colour=3)
    with pytest.raises(ValueError):
        get_strategy("no_existe")
    assert get_strategy("sma_crossover", fast="20", slow="50").params == {"fast": 20, "slow": 50}


def test_demo_csv_example_runs_and_is_flagged_simulated(root):
    svc = BacktestService(registry=ProviderRegistry([CsvProvider(root / "data" / "examples")]))
    rep = svc.run("DEMO-EJEMPLO", "sma_crossover", {}, BacktestConfig())
    assert rep.is_simulated_data is True
    assert "SIMULADOS" in rep.transparency.data["warning"]
