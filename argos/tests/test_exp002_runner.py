"""TESTS DE INTEGRACIÓN del ejecutor de EXP-002 con datos SIMULADOS (ficheros DEMO-*).

Recorren carga de datos → calendario → GEM → motor → métricas → criterios → informe, en carpetas temporales.
Ninguno lee data/csv/, ni escribe en data/experiments/, ni usa datos reales. Los veredictos que salen aquí
no tienen ningún valor sobre GEM: solo prueban que el procedimiento hace lo que dice el protocolo.
"""

import json
import math
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from argos.backtest.portfolio import InsufficientCashError, Market, max_drawdown
from argos.data.calendar_us import sessions
from argos.experiments import exp002
from argos.experiments.protocol import ProtocolChangedError, load_protocol
from argos.strategy.gem import gem_decisions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def protocol():
    p, sha, path = load_protocol("EXP-002")
    return p, sha, exp002.load_raw_protocol(path)


@pytest.fixture(scope="module")
def dataset(tmp_path_factory, protocol):
    d = tmp_path_factory.mktemp("exp002-demo")
    mapping = exp002.write_synthetic_dataset(protocol[0], d)
    return d, mapping


@pytest.fixture(scope="module")
def market(dataset, protocol):
    d, mapping = dataset
    m, info = exp002.load_market(protocol[0], d, mapping, audit=True)
    return m, info


@pytest.fixture
def lab(tmp_path):
    """Copia de protocols/ (con su LOCKS.json) y carpetas de resultados temporales."""
    pdir = tmp_path / "protocols"
    shutil.copytree(ROOT / "protocols", pdir)
    return pdir, tmp_path / "resultados"


def edit_csv(src_dir, mapping, ticker, dst_dir, fn):
    shutil.copytree(src_dir, dst_dir)
    path = dst_dir / f"{mapping[ticker]}.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(fn(lines)) + "\n", encoding="utf-8")
    return dst_dir


# ------------------------------------------------------------------ datos y calendario


def test_market_uses_exactly_the_nyse_sessions_of_the_protocol(market):
    m, info = market
    assert list(m.sessions) == sessions(date(2007, 6, 1), date(2026, 9, 30))
    assert m.tickers == ["AGG", "BIL", "SPY", "VEU"]
    assert all(a.simulated and a.quality != "bloqueado" for a in info)


@pytest.mark.parametrize("case, fn, needle", [
    ("falta_sesion", lambda L: L[:100] + L[101:], "faltan 1 sesiones NYSE"),
    ("fecha_no_nyse", lambda L: L[:1] + ["2015-07-04,1,1,1,1,1"] + L[1:], "no son sesión NYSE"),
    ("reserva_2026", lambda L: L + ["2026-10-01,100,101,99,100,1000"], "fuera de 2007-06-01"),
    ("precio_negativo", lambda L: L[:50] + [L[50].split(",")[0] + ",-5,1,-6,-5,1000"] + L[51:], "bloqueado"),
    ("texto_no_numerico", lambda L: L[:50] + [L[50].split(",")[0] + ",abc,1,1,1,1"] + L[51:], "no es un número"),
])
def test_bad_data_stops_and_is_never_filled(dataset, protocol, tmp_path, case, fn, needle):
    src, mapping = dataset
    d = edit_csv(src, mapping, "VEU", tmp_path / case, fn)
    with pytest.raises(exp002.InconclusiveError) as exc:
        exp002.load_market(protocol[0], d, mapping)
    assert any(needle in r for r in exc.value.reasons), exc.value.reasons
    assert any(r.startswith("VEU") for r in exc.value.reasons)


def test_missing_file_is_inconclusive(dataset, protocol, tmp_path):
    src, mapping = dataset
    d = tmp_path / "sin_bil"
    shutil.copytree(src, d)
    (d / f"{mapping['BIL']}.csv").unlink()
    with pytest.raises(exp002.InconclusiveError, match="BIL"):
        exp002.load_market(protocol[0], d, mapping)


# ------------------------------------------------------------------ simulación por tramo


def main_cfg(protocol):
    return exp002.configs_from_protocol(protocol[0], protocol[2])[0]


def test_configs_match_the_locked_protocol(protocol):
    cfgs = {c.id: c for c in exp002.configs_from_protocol(protocol[0], protocol[2])}
    base = cfgs["principal"]
    assert (base.capital, base.min_commission, base.slippage, base.commission_pct, base.lookback, base.timing,
            base.variant) == (100.0, 1.0, 0.0005, 0.0, 12, "open", "principal")
    text = {v["id"]: v["change"] for v in protocol[2]["sensitivity"]["variants"]}
    assert cfgs["S1"].variant == "S1" and "GANADOR" in text["S1"]
    assert cfgs["S2"].lookback == 6 and "= 6" in text["S2"]
    assert cfgs["S3"].lookback == 9 and "= 9" in text["S3"]
    assert (cfgs["S4"].min_commission, cfgs["S4"].slippage) == (2.0, 0.0010) and "m = 2" in text["S4"] and "0,0010" in text["S4"]
    assert cfgs["S5"].capital == 50 and "50" in text["S5"]
    assert cfgs["S6"].capital == 200 and "200" in text["S6"]
    assert cfgs["S7"].capital == 10_000 and "10.000" in text["S7"]
    assert cfgs["S8"].timing == "close" and "CIERRE" in text["S8"]
    for k, c in cfgs.items():  # cada variante cambia solo lo suyo
        changed = {f for f in ("variant", "lookback", "min_commission", "slippage", "capital", "timing")
                   if getattr(c, f) != getattr(base, f)}
        assert changed == set(exp002.VARIANT_CHANGES[k]), k


def test_evaluation_period_decisions_execution_and_liquidation(market, protocol):
    m, _ = market
    cfg = main_cfg(protocol)
    decs = gem_decisions(m, 12)
    pr = exp002.run_period(m, decs, "evaluacion", date(2015, 1, 1), date(2025, 12, 31), cfg)
    assert pr.decisions_count == 132
    assert (pr.initial_decision.date, m.sessions[pr.first_index], m.sessions[pr.last_index]) == (
        date(2014, 12, 31), date(2015, 1, 2), date(2025, 12, 31))
    gem = pr.runs["gem"]
    entry = gem.orders[0]
    assert (entry.date, entry.kind, entry.timing, entry.ticker) == (date(2015, 1, 2), "entrada", "open", pr.initial_decision.target)
    for o in gem.orders:
        if o.kind == "cambio":
            assert o.date == m.sessions[m.index_of(o.decision_date) + 1] and o.timing == "open"
    last = [o for o in gem.orders if o.kind == "liquidación"]
    assert len(last) == 1 and (last[0].date, last[0].timing) == (date(2025, 12, 31), "close")
    assert date(2025, 12, 31) not in {o.decision_date for o in gem.orders}  # decisión de dic-2025: no se ejecuta
    assert len(gem.orders) == 2 + 2 * gem.switches
    assert exp002.accounting_problems(m, pr, cfg) == []


def test_metrics_follow_protocol_definitions(market, protocol):
    m, _ = market
    cfg = main_cfg(protocol)
    pr = exp002.run_period(m, gem_decisions(m, 12), "evaluacion", date(2015, 1, 1), date(2025, 12, 31), cfg)
    for key, run in pr.runs.items():
        got = exp002.portfolio_metrics(m, pr, key)
        v = run.values
        peak, mdd = v[0], 0.0
        for x in v:  # MaxDD a mano, con V_0 y todas las sesiones
            peak = max(peak, x)
            mdd = max(mdd, 1 - x / peak)
        assert got["max_drawdown"] == pytest.approx(mdd) == pytest.approx(max_drawdown(v))
        days = (run.dates[-1] - run.dates[0]).days
        assert got["cagr"] == pytest.approx((v[-1] / 100) ** (365.25 / days) - 1)
        bil = m.closes["BIL"][pr.first_index - 1: pr.last_index + 1]
        e = np.diff(v) / np.array(v[:-1]) - np.diff(bil) / bil[:-1]
        assert got["sharpe_excess"] == pytest.approx(e.mean() / e.std(ddof=1) * math.sqrt(252))
        assert got["orders"] == len(run.orders) and got["commissions"] == len(run.orders) * 1.0
        assert sum(got["fraction_of_sessions"].values()) == pytest.approx(1.0 if key != "pasiva_30_30_40" else 3.0)


def test_identical_methodology_when_gem_never_switches(protocol):
    """Si SPY lidera siempre, GEM no cambia nunca (K = 0) y su curva es idéntica a la de comprar y mantener SPY."""
    days = sessions(date(2007, 6, 1), date(2016, 12, 30))
    n = len(days)
    g = lambda r: 100 * np.cumprod(np.full(n, 1 + r))  # noqa: E731
    closes = {"SPY": g(0.0008), "VEU": g(0.0003), "AGG": g(0.0001), "BIL": g(0.00002)}
    mkt = Market(tuple(days), {t: c * 0.999 for t, c in closes.items()}, closes)
    pr = exp002.run_period(mkt, gem_decisions(mkt, 12), "evaluacion", date(2015, 1, 1), date(2016, 12, 30),
                           main_cfg(protocol))
    gem, spy = pr.runs["gem"], pr.runs["spy_buy_hold"]
    assert gem.switches == 0 and len(gem.orders) == 2
    assert gem.values == spy.values and gem.commissions == spy.commissions == 2.0


def test_close_timing_variant_s8(market, protocol):
    m, _ = market
    cfg = replace(main_cfg(protocol), id="S8", timing="close")
    pr = exp002.run_period(m, gem_decisions(m, 12), "evaluacion", date(2015, 1, 1), date(2025, 12, 31), cfg)
    entry = pr.runs["gem"].orders[0]
    assert (entry.date, entry.timing) == (date(2015, 1, 2), "open")  # la entrada sigue la regla del tramo
    for o in pr.runs["gem"].orders:
        if o.kind == "cambio":
            assert o.date == o.decision_date and o.timing == "close"
    assert exp002.accounting_problems(m, pr, cfg) == []


def test_insufficient_capital_is_reported_not_forced(market, protocol):
    m, _ = market
    cfg = replace(main_cfg(protocol), capital=1.0)
    with pytest.raises(InsufficientCashError):
        exp002.run_period(m, gem_decisions(m, 12), "evaluacion", date(2015, 1, 1), date(2025, 12, 31), cfg)


def test_period_without_sessions_or_prior_decision(market, protocol):
    m, _ = market
    cfg = main_cfg(protocol)
    with pytest.raises(exp002.InconclusiveError, match="No hay sesiones"):
        exp002.run_period(m, gem_decisions(m, 12), "x", date(2030, 1, 1), date(2030, 12, 31), cfg)
    with pytest.raises(exp002.InconclusiveError, match="ninguna decisión GEM anterior"):
        exp002.run_period(m, gem_decisions(m, 12), "x", date(2008, 1, 1), date(2008, 12, 31), cfg)


def test_lookahead_audit_passes_and_detects_leaks(market, protocol, monkeypatch):
    m, _ = market
    cfg = main_cfg(protocol)
    assert exp002.lookahead_audit(m, cfg)["ok"]
    real = exp002.gem_decisions

    def leaky(mkt, lookback=12, variant="principal"):  # una señal que mira la sesión siguiente
        out = real(mkt, lookback, variant)
        return [replace(d, target="AGG") if d.index + 1 < len(mkt.sessions) and
                mkt.closes["SPY"][d.index + 1] < mkt.closes["SPY"][d.index] else d for d in out]

    monkeypatch.setattr(exp002, "gem_decisions", leaky)
    res = exp002.lookahead_audit(m, cfg)
    assert not res["ok"] and res["mismatches"]


# ------------------------------------------------------------------ incertidumbre


def test_block_bootstrap_is_reproducible_and_sane():
    rng = np.random.default_rng(1)
    a = rng.normal(0.01, 0.04, 132)
    bil = np.full(132, 0.001)
    r1 = exp002.block_bootstrap(a, a, bil, replicas=500)
    assert r1["delta_cagr"] == {"low": 0.0, "high": 0.0} and r1["delta_max_drawdown"] == {"low": 0.0, "high": 0.0}
    better = exp002.block_bootstrap(a + 0.005, a, bil, replicas=500)
    assert better["delta_cagr"]["low"] > 0
    assert exp002.block_bootstrap(a + 0.005, a, bil, replicas=500) == better  # misma semilla, mismo resultado
    with pytest.raises(exp002.Exp002Error):
        exp002.block_bootstrap(a[:10], a[:10], bil[:10])


# ------------------------------------------------------------------ ejecutor completo


def test_full_rehearsal_writes_only_to_its_own_folder(dataset, lab, monkeypatch, tmp_path):
    from argos.data.sources import tiingo

    exp001_csv = tmp_path / "csv_exp001"
    exp001_csv.mkdir()
    monkeypatch.setattr(tiingo, "CSV_DIR", exp001_csv)
    pdir, results = lab
    src, mapping = dataset
    r = exp002.run_exp002(csv_dir=src, results_dir=results, dry_run=True, ticker_files=mapping, protocol_dir=pdir)
    assert r["dry_run"] is True and r["verdict"] in exp002.VERDICT_TEXT
    assert all(a["ok"] for a in r["lookahead"])
    assert all(p["accounting_ok"] for c in r["configs"].values() for p in c["periods"].values())
    assert r["configs"]["principal"]["periods"]["evaluacion"]["decisions"] == 132
    assert set(r["configs"]) == set(exp002.VARIANT_CHANGES)
    report = (Path(r["folder"]) / "report.md").read_text(encoding="utf-8")
    assert report.startswith("# ENSAYO CON DATOS SIMULADOS") and "NO tiene ningún valor" in report
    assert "funciona" not in report.replace("el procedimiento funciona", "")
    reg = (results / "registry.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(reg) == 1 and json.loads(reg[0])["dry_run"] is True
    assert Path(r["folder"]).parent == results / "ensayos"
    assert list(exp001_csv.iterdir()) == []  # nada escrito en la carpeta de EXP-001


def test_real_mode_refuses_simulated_files(dataset, lab):
    pdir, results = lab
    src, mapping = dataset
    r = exp002.run_exp002(csv_dir=src, results_dir=results, dry_run=False, ticker_files=mapping, protocol_dir=pdir,
                          raw_dir=results / "raw-vacio")
    assert r["verdict"] == "inconcluso"
    assert any("SIMULADOS" in x or "auditoría" in x for x in r["inconclusive_reasons"])
    assert "configs" not in r  # no se ha simulado nada


def test_altered_protocol_or_registry_blocks_the_run(dataset, lab):
    pdir, results = lab
    src, mapping = dataset
    p = pdir / "EXP-002.json"
    p.write_bytes(p.read_bytes().replace(b'"lookback_months": 12', b'"lookback_months": 10'))
    with pytest.raises(ProtocolChangedError):
        exp002.run_exp002(csv_dir=src, results_dir=results, dry_run=True, ticker_files=mapping, protocol_dir=pdir)
    shutil.copy(ROOT / "protocols" / "EXP-002.json", p)
    results.mkdir(parents=True)
    (results / "registry.jsonl").write_text(json.dumps({"dry_run": False, "protocol_sha256": "x" * 64}) + "\n",
                                            encoding="utf-8")
    with pytest.raises(ProtocolChangedError, match="EXP-003"):
        exp002.run_exp002(csv_dir=src, results_dir=results, dry_run=True, ticker_files=mapping, protocol_dir=pdir)


def test_cli_without_flags_only_checks_and_simulates_nothing(capsys, tmp_path, monkeypatch):
    from argos.data.sources import tiingo

    monkeypatch.setattr(tiingo, "CSV_DIR", tmp_path / "csv")
    assert exp002.main([]) == 0
    out = capsys.readouterr().out
    assert "coincide con LOCKS.json" in out and "No se ha simulado nada" in out
    assert str(tmp_path / "csv" / "EXP-002") in out
