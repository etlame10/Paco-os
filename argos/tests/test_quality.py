"""Control de integridad de datos: cada problema se detecta y se avisa, nunca se corrige."""

import math
import random
from datetime import date, datetime, timedelta, timezone

import pytest

from argos.core.models import Bar, PriceHistory, Provenance
from argos.data.quality import QualityRequirements, assess_quality


def series(start=date(2010, 1, 4), years=11, seed=1):
    rng = random.Random(seed)
    out, d, p = [], start, 100.0
    end = start + timedelta(days=int(365.25 * years))
    while d <= end:
        if d.weekday() < 5:
            c = p * math.exp(rng.gauss(0.0003, 0.01))
            out.append(Bar(date=d, open=p, high=max(p, c) * 1.005, low=min(p, c) * 0.995, close=c, volume=1000))
            p = c
        d += timedelta(days=1)
    return out


def hist(bars):
    return PriceHistory(ticker="TEST", bars=bars, provenance=Provenance(
        provider="t", source_description="t", is_simulated=False, retrieved_at=datetime.now(timezone.utc)))


def check(report, cid):
    return next(c for c in report.checks if c.id == cid)


def test_clean_long_series_passes():
    r = assess_quality(hist(series()))
    assert r.status == "superado", [(c.id, c.detail) for c in r.checks if c.status != "ok"]
    assert len(r.checks) == 13


def scaled(bars, i, factor):
    """Multiplica los precios desde la barra i (como haría un split sin ajustar)."""
    return bars[:i] + [b.model_copy(update={k: getattr(b, k) * factor for k in ("open", "high", "low", "close")})
                       for b in bars[i:]]


def test_unadjusted_split_blocks():
    bars = scaled(series(), 1000, 0.5)  # split 2:1 sin ajustar
    r = assess_quality(hist(bars))
    assert r.status == "bloqueado" and check(r, "splits").status == "bloqueo"
    assert "split 2:1" in check(r, "splits").examples[0]


def test_reverse_split_detected():
    r = assess_quality(hist(scaled(series(), 1000, 10)))
    assert check(r, "splits").status == "bloqueo" and "contrasplit 10:1" in check(r, "splits").examples[0]


def test_big_jump_without_split_ratio_warns():
    r = assess_quality(hist(scaled(series(), 1000, 0.55)))  # −45%, no es proporción de split
    assert check(r, "splits").status == "ok"
    assert check(r, "saltos").status == "aviso" and r.status == "con avisos"


@pytest.mark.parametrize("gap_days, status", [(10, "aviso"), (30, "bloqueo")])
def test_gaps(gap_days, status):
    bars = series()
    d0 = bars[500].date
    bars = [b for b in bars if not (d0 < b.date < d0 + timedelta(days=gap_days))]
    assert check(assess_quality(hist(bars)), "huecos").status == status


def test_incoherent_ohlc():
    bars = series()
    bars[100] = bars[100].model_copy(update={"high": bars[100].low * 0.9})
    assert check(assess_quality(hist(bars)), "ohlc").status == "aviso"
    many = [b.model_copy(update={"high": b.low * 0.9}) if i % 20 == 0 else b for i, b in enumerate(series())]
    assert check(assess_quality(hist(many)), "ohlc").status == "bloqueo"


def test_impossible_values():
    bars = series()
    bars[10] = bars[10].model_copy(update={"low": -1.0})
    r = assess_quality(hist(bars))
    assert check(r, "precios_positivos").status == "bloqueo" and r.blocked


def test_volume_checks():
    no_vol = [b.model_copy(update={"volume": 0}) for b in series()]
    assert check(assess_quality(hist(no_vol)), "volumen").status == "aviso"
    neg = series()
    neg[5] = neg[5].model_copy(update={"volume": -10})
    assert check(assess_quality(hist(neg)), "volumen").status == "bloqueo"


def test_stale_prices_warn():
    bars = series()
    frozen = bars[200]
    bars = bars[:200] + [b.model_copy(update={k: getattr(frozen, k) for k in ("open", "high", "low", "close")})
                         for b in bars[200:207]] + bars[207:]
    assert check(assess_quality(hist(bars)), "precios_congelados").status == "aviso"


def test_missing_sessions_in_year_warn():
    bars = [b for b in series() if not (b.date.year == 2013 and b.date.month in (3, 4))]
    r = assess_quality(hist(bars))
    assert check(r, "sesiones_por_anio").status == "aviso"
    assert any("2013" in e for e in check(r, "sesiones_por_anio").examples)


def test_frequency_weekly_blocks():
    weekly = series()[::5]
    assert check(assess_quality(hist(weekly)), "frecuencia").status == "bloqueo"


def test_duplicates_and_future_dates():
    bars = series()
    dup = bars + [bars[3]]
    assert check(assess_quality(hist(dup)), "duplicados").status == "bloqueo"
    future = bars + [bars[-1].model_copy(update={"date": date.today() + timedelta(days=10)})]
    assert check(assess_quality(hist(future)), "fechas").status == "bloqueo"


def test_length_requirements():
    req = QualityRequirements(required_start=date(2007, 1, 1), required_end=date(2025, 12, 31), min_years=10)
    r = assess_quality(hist(series(start=date(2010, 1, 4), years=11)), req)
    c = check(r, "longitud")
    assert c.status == "bloqueo" and "2007-01-01" in c.detail and "2025-12-31" in c.detail
    short = assess_quality(hist(series(years=3)))
    assert check(short, "longitud").status == "aviso"


def test_empty_history_blocks():
    r = assess_quality(hist([]))
    assert r.blocked and r.n_bars == 0


def test_quality_never_modifies_data():
    bars = scaled(series(), 1000, 0.5)
    h = hist(bars)
    before = [b.model_dump() for b in h.bars]
    assess_quality(h)
    assert [b.model_dump() for b in h.bars] == before


def test_backtest_report_includes_quality_and_warns():
    from argos.backtest.models import BacktestConfig
    from argos.backtest.service import BacktestService
    from argos.data.providers.demo import DemoProvider
    from argos.data.registry import ProviderRegistry

    rep = BacktestService(registry=ProviderRegistry([DemoProvider()])).run(
        "DEMO-LATERAL", "sma_crossover", {}, BacktestConfig())
    assert rep.data_quality.status == "con avisos"  # solo 2 años de datos
    assert any("Control de calidad" in n and "Menos de 10 años" in n for n in rep.notes)


def test_check_cli_exit_codes(tmp_path, capsys):
    from argos.data.check import main

    assert main(["--dir", str(tmp_path)]) == 1  # carpeta vacía
    assert main(["--dir", str(tmp_path), "SPY"]) == 1  # falta el fichero
    lines = ["date,open,high,low,close,volume"] + [
        f"{b.date},{b.open},{b.high},{b.low},{b.close},{b.volume}" for b in series()]
    (tmp_path / "OKAY.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert main(["--dir", str(tmp_path), "OKAY"]) == 0
    assert "NO DOCUMENTADA" in capsys.readouterr().out
    split = scaled(series(), 1000, 0.5)
    (tmp_path / "SPLIT.csv").write_text("\n".join(
        ["date,open,high,low,close,volume"] + [f"{b.date},{b.open},{b.high},{b.low},{b.close},{b.volume}" for b in split]) + "\n", encoding="utf-8")
    assert main(["--dir", str(tmp_path), "SPLIT"]) == 1
