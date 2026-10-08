"""Registro de experimentos, protocolo pre-registrado, regímenes, criterios e informe."""

import json
import math
import re
import shutil
from datetime import date

import pytest

from argos.backtest.models import BacktestConfig
from argos.backtest.service import BacktestService
from argos.data.providers.csv_provider import CsvProvider
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry
from argos.experiments.dryrun import write_demo_dataset
from argos.experiments.protocol import ProtocolChangedError, load_protocol
from argos.experiments.regimes import classify, summarize_regimes, yearly_results
from argos.experiments.registry import ExperimentRegistry
from argos.experiments.report import render_markdown
from argos.experiments.runner import PeriodRow, _criterion, drawdown_better, run_experiment, sharpe_better
from argos.tools.adjust_csv import adjust

FORBIDDEN_PHRASES = [
    "la estrategia funciona", "estrategia ganadora", "recomendamos", "te recomiendo", "deberías comprar",
    "deberías vender", "compra ahora", "vende ahora", "garantiza", "beneficio asegurado",
]


# ----------------------------------------------------------------- protocolo


def test_protocol_exp001_is_fixed_as_registered(root):
    protocol, sha, path = load_protocol("EXP-001")
    assert protocol.strategy == {"name": "sma_crossover", "params": {"fast": 50, "slow": 200}}
    assert protocol.costs == {"initial_capital": 10000, "commission_pct": 0.001, "slippage_pct": 0.0005}
    assert [p.name for p in protocol.periods] == ["desarrollo", "fuera_de_muestra"]
    dev, oos = protocol.periods
    assert dev.end < oos.start  # sin solapamiento
    assert oos.end < date.fromisoformat(protocol.reserved_holdout["start"])
    assert [a.ticker for a in protocol.assets if a.core] == ["SPY", "KO", "AAPL", "XOM"]
    assert len(sha) == 64


@pytest.fixture
def lab(tmp_path):
    """Protocolo copiado, carpeta de datos con series SINTÉTICAS (nombre sin DEMO- solo para el test) y registro."""
    pdir = tmp_path / "protocols"
    pdir.mkdir()
    shutil.copy(load_protocol("EXP-001")[2], pdir / "EXP-001.json")
    shutil.copy(load_protocol("EXP-001")[2].parent / "LOCKS.json", pdir / "LOCKS.json")
    data = tmp_path / "csv"
    data.mkdir()
    protocol, _, _ = load_protocol("EXP-001", pdir)
    mapping = write_demo_dataset(protocol, data)
    for real, demo in mapping.items():  # renombrar para simular ficheros "reales" en el test
        (data / f"{demo}.csv").rename(data / f"{real}.csv")
        (data / f"{demo}.source.txt").rename(data / f"{real}.source.txt")
    return pdir, data, ExperimentRegistry(tmp_path / "registry.jsonl")


def test_protocol_lock_refuses_changed_protocol(lab):
    pdir, data, reg = lab
    res = run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir)
    assert len(res.rows) == 12 and not res.dry_run
    # Alguien "retoca" el protocolo después de ver resultados → debe negarse.
    p = pdir / "EXP-001.json"
    doc = json.loads(p.read_text())
    doc["strategy"]["params"]["fast"] = 40
    p.write_text(json.dumps(doc))
    with pytest.raises(ProtocolChangedError):
        run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir)


def test_dry_run_does_not_consume_lock(lab, tmp_path):
    pdir, data, reg = lab
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    protocol, _, _ = load_protocol("EXP-001", pdir)
    mapping = write_demo_dataset(protocol, demo_dir)
    res = run_experiment("EXP-001", data_dir=demo_dir, registry=reg, protocol_dir=pdir, dry_run=True, ticker_map=mapping)
    assert res.dry_run and all(r.dry_run for r in reg.list())
    assert reg.list(include_dry_runs=False) == []


def test_real_run_rejects_simulated_files(lab, tmp_path):
    pdir, _, reg = lab
    demo_dir = tmp_path / "demo2"
    demo_dir.mkdir()
    protocol, _, _ = load_protocol("EXP-001", pdir)
    mapping = write_demo_dataset(protocol, demo_dir)
    res = run_experiment("EXP-001", data_dir=demo_dir, registry=reg, protocol_dir=pdir, ticker_map=mapping)
    assert res.rows == []
    assert all(a.status == "error" and "SIMULADO" in a.detail for a in res.assets)


def test_missing_and_blocked_assets_are_reported_not_hidden(lab):
    pdir, data, reg = lab
    (data / "KO.csv").unlink()
    # AAPL con un split 2:1 sin ajustar a mitad de la serie
    lines = (data / "AAPL.csv").read_text().splitlines()
    head, rows = lines[0], lines[1:]
    fixed = rows[:2000]
    for row in rows[2000:]:
        d, *vals = row.split(",")
        o, h, l, c = (float(v) / 2 for v in vals[:4])
        fixed.append(f"{d},{o},{h},{l},{c},{vals[4]}")
    (data / "AAPL.csv").write_text("\n".join([head, *fixed]) + "\n")
    res = run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir)
    status = {a.ticker: a.status for a in res.assets}
    assert status["KO"] == "sin datos" and status["AAPL"] == "bloqueado por calidad"
    assert {r.ticker for r in res.rows} == {"SPY", "XOM", "GLD", "EFA"}
    md = render_markdown(res)
    assert "sin datos" in md and "bloqueado por calidad" in md and "split 2:1" in md
    # Con solo 2 activos principales válidos (< 3), los criterios no son evaluables.
    assert all(c.met is None for c in res.criteria)
    assert "NO EVALUABLE" in md


def test_registry_records_everything_needed(lab):
    pdir, data, reg = lab
    run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir)
    recs = reg.list(experiment_id="EXP-001")
    assert len(recs) == 12
    r = recs[0]
    assert r.recorded_at and r.argos_version and r.protocol_sha256 and r.period_name in ("desarrollo", "fuera_de_muestra")
    assert r.ticker and r.strategy == "sma_crossover" and r.params == {"fast": 50, "slow": 200}
    assert r.initial_capital == 10000 and r.commission_pct == 0.001 and r.slippage_pct == 0.0005
    assert r.data_sha256 and len(r.data_sha256) == 64
    for key in ("total_return", "annualized_return", "max_drawdown", "volatility", "sharpe", "n_trades",
                "win_rate", "best_trade_return", "worst_trade_return", "exposure", "final_capital"):
        assert key in r.strategy_metrics and key in r.benchmark_metrics
    assert r.lookahead_audit_passed


def test_registry_is_append_only(tmp_path):
    reg = ExperimentRegistry(tmp_path / "r.jsonl")
    svc = BacktestService(registry=ProviderRegistry([DemoProvider()]))
    rep = svc.run("DEMO-LATERAL", "sma_crossover", {}, BacktestConfig())
    a = reg.record(rep)
    first_line = reg.path.read_text().splitlines()[0]
    b = reg.record(rep)
    lines = reg.path.read_text().splitlines()
    assert lines[0] == first_line and len(lines) == 2 and a.record_id != b.record_id
    assert a.dry_run is True  # datos simulados → siempre ensayo


# ----------------------------------------------------------------- regímenes y criterios


def test_regime_classification_thresholds():
    assert classify(0.15, 0.10, -0.10) == "alcista"
    assert classify(-0.2, 0.10, -0.10) == "bajista"
    assert classify(0.05, 0.10, -0.10) == "lateral"
    assert classify(0.10, 0.10, -0.10) == "lateral"  # el umbral no se incluye


def test_yearly_returns_compound_to_total(lab):
    _, data, _ = lab
    svc = BacktestService(registry=ProviderRegistry([CsvProvider(data)]))
    rep = svc.run("XOM", "sma_crossover", {}, BacktestConfig(start=date(2008, 1, 1), end=date(2016, 12, 31)))
    ys = yearly_results(rep, "desarrollo", 0.10, -0.10)
    assert [y.year for y in ys] == list(range(2008, 2017))
    assert math.prod(1 + y.strategy_return for y in ys) - 1 == pytest.approx(rep.strategy.metrics.total_return)
    assert math.prod(1 + y.benchmark_return for y in ys) - 1 == pytest.approx(rep.benchmark.metrics.total_return)
    summ = summarize_regimes(ys)
    assert sum(g.n_years for g in summ) == 9


def row(ticker, sharpe_s, sharpe_b, dd_s=-0.1, dd_b=-0.2, core=True):
    return PeriodRow(ticker=ticker, role="x", core=core, period_name="fuera_de_muestra", start="2017", end="2025",
                     strategy_return=0, benchmark_return=0, difference=0, strategy_cagr=None, benchmark_cagr=None,
                     strategy_final=1, benchmark_final=1, strategy_max_dd=dd_s, benchmark_max_dd=dd_b,
                     strategy_vol=None, benchmark_vol=None, strategy_sharpe=sharpe_s, benchmark_sharpe=sharpe_b,
                     n_trades=1, win_rate=None, best_trade=None, worst_trade=None, exposure=0.5, record_id="x")


def test_criterion_predicates():
    assert sharpe_better(row("A", 0.8, 0.5)) is True
    assert sharpe_better(row("A", 0.4, 0.5)) is False
    assert sharpe_better(row("A", None, 0.5)) is None
    # Caídas negativas: −10% es MENOR caída que −30%.
    assert drawdown_better(row("A", 1, 1, dd_s=-0.10, dd_b=-0.30)) is True
    assert drawdown_better(row("A", 1, 1, dd_s=-0.40, dd_b=-0.30)) is False


def test_criteria_counting():
    better = sharpe_better
    rows = [row("A", 1, 0.5), row("B", 1, 0.5), row("C", 0.2, 0.5), row("D", 1, 0.5), row("E", 9, 0, core=False)]
    c = _criterion(rows, "p", "t", better, 3, 3)
    assert (c.count, c.total, c.met) == (3, 4, True)  # el complementario E no cuenta
    rows[3] = row("D", 0.1, 0.5)
    assert _criterion(rows, "p", "t", better, 3, 3).met is False
    few = [row("A", 1, 0.5), row("B", None, 0.5)]
    assert _criterion(few, "p", "t", better, 3, 3).met is None


# ----------------------------------------------------------------- informe y lenguaje


def test_report_language_is_descriptive_not_prescriptive(lab):
    pdir, data, reg = lab
    md = render_markdown(run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir))
    low = md.lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in low, phrase
    assert "en esta muestra histórica, la estrategia obtuvo" in low
    assert "no es una recomendación de inversión" in low
    assert "## 9. qué conclusiones podemos sacar" in low and "## 10. qué conclusiones no podemos sacar" in low
    for section in ("## 1-3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8."):
        assert section in md


def test_dry_run_report_is_clearly_labelled(tmp_path):
    protocol, _, _ = load_protocol("EXP-001")
    mapping = write_demo_dataset(protocol, tmp_path)
    res = run_experiment("EXP-001", data_dir=tmp_path, registry=ExperimentRegistry(tmp_path / "r.jsonl"),
                         dry_run=True, ticker_map=mapping)
    md = render_markdown(res)
    assert md.count("SIMULADO") >= 3 and "ENSAYO CON DATOS SIMULADOS" in md
    assert "no dicen nada del mercado real" in md


def test_report_without_data_concludes_nothing(tmp_path):
    res = run_experiment("EXP-001", data_dir=tmp_path, registry=ExperimentRegistry(tmp_path / "r.jsonl"))
    assert res.rows == [] and all(a.status == "sin datos" for a in res.assets)
    md = render_markdown(res)
    assert "No se ha ejecutado ningún backtest" in md
    assert "Ninguna sobre la estrategia" in md


def test_comparison_verdicts_never_say_it_works():
    from argos.backtest import comparison

    src = re.sub(r"\s+", " ", open(comparison.__file__, encoding="utf-8").read().lower())
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in src.replace("no garantiza", ""), phrase  # la advertencia negada sí debe estar


# ----------------------------------------------------------------- herramienta de ajuste


def test_adjust_csv_applies_factor_to_all_prices(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-02,100,110,90,100,50,1000\n"
                   "2024-01-03,100,104,98,102,102,2000\n")
    dst = tmp_path / "out" / "KO.csv"
    assert adjust(src, dst) == 2
    lines = dst.read_text().splitlines()
    assert lines[0] == "date,open,high,low,close,volume"
    assert lines[1] == "2024-01-02,50.000000,55.000000,45.000000,50.000000,1000"
    assert lines[2] == "2024-01-03,100.000000,104.000000,98.000000,102.000000,2000"
    assert "Adj Close / Close" in dst.with_suffix(".source.txt").read_text()
    assert len(CsvProvider(dst.parent).get_price_history("KO").bars) == 2


def test_adjust_csv_refuses_incomplete_rows(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-02,null,110,90,100,50,1000\n")
    with pytest.raises(SystemExit, match="línea 2"):
        adjust(src, tmp_path / "o.csv")


def test_preregistration_lock_protects_before_first_real_run(lab):
    """Aunque el registro esté VACÍO, un protocolo editado no se ejecuta (LOCKS.json)."""
    from argos.experiments.protocol import check_preregistered

    pdir, data, reg = lab
    p = pdir / "EXP-001.json"
    p.write_text(p.read_text().replace('"fast": 50', '"fast": 45'))
    assert reg.list() == []
    with pytest.raises(ProtocolChangedError, match="no coincide con el pre-registrado"):
        run_experiment("EXP-001", data_dir=data, registry=reg, protocol_dir=pdir)
    assert reg.list() == []  # no se registró nada
    (pdir / "LOCKS.json").unlink()
    with pytest.raises(ProtocolChangedError, match="Falta LOCKS.json"):
        check_preregistered("EXP-001", "x" * 64, pdir)
    with pytest.raises(ProtocolChangedError, match="no figura"):
        (pdir / "LOCKS.json").write_text("{}")
        check_preregistered("EXP-001", "x" * 64, pdir)


def test_locks_file_matches_committed_protocol(root):
    import hashlib

    locks = json.loads((root / "protocols" / "LOCKS.json").read_text())
    actual = hashlib.sha256((root / "protocols" / "EXP-001.json").read_bytes()).hexdigest()
    assert locks["EXP-001"]["sha256"] == actual == "7f553e110fff59245a96504bdd0107b179550164eaf3800cbe8664f34cc98cce"
    assert locks["EXP-001"]["preregistration_commit"] == "6b230de"
