"""TESTS DE INTEGRACIÓN: los datos de EXP-002 nunca se mezclan con los de EXP-001.

Usa un Tiingo FALSO (sin red, sin clave real) y carpetas temporales. No toca data/ del repositorio.
"""

from datetime import date, timedelta

import pytest

from argos.data.sources import tiingo
from argos.experiments.storage import (
    StorageError,
    check_csv_dir,
    csv_dir_for,
    download_for_range,
    results_dir_for,
)
from argos.tools import tiingo as cli
from tests.synthetic_tiingo import HEADER
from tests.test_tiingo import FIXED_NOW, KEY

EXP001 = (date(2007, 1, 1), date(2025, 12, 31))
EXP002 = (date(2007, 6, 1), date(2026, 9, 30))


def body(start, end):
    lines, d, p = [HEADER], start, 50.0
    while d <= end:
        if d.weekday() < 5:
            p *= 1.0002
            lines.append(f"{d},{p:.2f},{p * 1.01:.2f},{p * 0.99:.2f},{p:.2f},1000,{p:.4f},{p * 1.01:.4f},"
                         f"{p * 0.99:.4f},{p:.4f},1000,0.0,1.0")
        d += timedelta(days=1)
    return "\n".join(lines) + "\n"


class RangeTiingo:
    """Devuelve datos del rango pedido en la URL."""

    def __call__(self, url, headers):
        q = dict(x.split("=") for x in url.split("?")[1].split("&"))
        return 200, {}, body(date.fromisoformat(q["startDate"]), date.fromisoformat(q["endDate"])).encode()


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    raw, csv = tmp_path / "raw", tmp_path / "csv"
    monkeypatch.setattr(tiingo, "RAW_DIR", raw)
    monkeypatch.setattr(tiingo, "CSV_DIR", csv)
    monkeypatch.setenv("ARGOS_CSV_DIR", str(csv))
    return raw, csv


def dl(raw, ticker, rng):
    return tiingo.download_ticker(ticker, *rng, key=KEY, raw_dir=raw, fetch=RangeTiingo(), now=FIXED_NOW)


def test_folders_per_experiment(dirs):
    _, csv = dirs
    assert csv_dir_for("EXP-001") == csv and csv_dir_for("EXP-002") == csv / "EXP-002"
    assert results_dir_for("EXP-002").parts[-3:] == ("data", "experiments", "EXP-002")
    with pytest.raises(StorageError):
        results_dir_for("EXP-001")
    with pytest.raises(StorageError, match="carpeta de datos de EXP-001"):
        check_csv_dir("EXP-002", csv)
    check_csv_dir("EXP-001", csv)  # EXP-001 sigue usando la suya


def test_conversion_uses_the_download_with_the_protocol_range(dirs, capsys):
    raw, csv = dirs
    dl(raw, "SPY", EXP001)
    for t in ("SPY", "VEU", "AGG", "BIL"):
        dl(raw, t, EXP002)  # la descarga de EXP-002 de SPY es la MÁS RECIENTE
    assert download_for_range("SPY", *EXP001, raw)["start"] == "2007-01-01"
    assert download_for_range("SPY", *EXP002, raw)["start"] == "2007-06-01"

    cli.main(["convertir", "--protocolo", "EXP-002"])
    assert sorted(p.name for p in (csv / "EXP-002").glob("*.csv")) == ["AGG.csv", "BIL.csv", "SPY.csv", "VEU.csv"]
    assert not list(csv.glob("*.csv"))  # nada en la carpeta de EXP-001
    assert "2007-06-01 → 2026-09-30" in (csv / "EXP-002" / "SPY.source.txt").read_text(encoding="utf-8")

    cli.main(["convertir", "--protocolo", "EXP-001", "--tickers", "SPY"])
    src = (csv / "SPY.source.txt").read_text(encoding="utf-8")
    assert "2007-01-01 → 2025-12-31" in src  # EXP-001 convierte SU descarga, no la más reciente
    assert (csv / "SPY.csv").read_text(encoding="utf-8").splitlines()[-1].startswith("2025-12-31")
    exp001_before = (csv / "SPY.csv").read_bytes()
    cli.main(["convertir", "--protocolo", "EXP-002"])  # volver a convertir EXP-002 no toca el CSV de EXP-001
    assert (csv / "SPY.csv").read_bytes() == exp001_before
    capsys.readouterr()


def test_conversion_without_a_matching_download_stops(dirs, capsys):
    raw, csv = dirs
    dl(raw, "SPY", EXP001)  # solo existe la descarga de EXP-001
    assert cli.main(["convertir", "--protocolo", "EXP-002", "--tickers", "SPY"]) == 1
    assert "rango del protocolo (2007-06-01 → 2026-09-30)" in capsys.readouterr().out
    assert not (csv / "EXP-002" / "SPY.csv").exists()


def test_check_and_audit_default_to_the_experiment_folder(dirs, capsys):
    from argos.data import audit, check

    raw, csv = dirs
    for t in ("SPY", "VEU", "AGG", "BIL"):
        dl(raw, t, EXP002)
    cli.main(["convertir", "--protocolo", "EXP-002"])
    capsys.readouterr()
    check.main(["--protocolo", "EXP-002"])
    assert "No existe" not in capsys.readouterr().out
    audit.main(["--protocolo", "EXP-002", "--raw-dir", str(raw)])
    out = capsys.readouterr().out
    assert "SPY" in out and "No existe" not in out


def test_dividends_and_splits_reach_the_engine_as_total_return(tmp_path):
    """Original sintético con dividendos trimestrales y un split → conversión mecánica (adj*) → motor.
    Con costes cero, comprar y mantener rinde exactamente la rentabilidad total calculada a mano con los precios SIN
    ajustar, los dividendos cobrados y el split."""
    import numpy as np

    from argos.backtest.portfolio import CostModel, Execution, Market, simulate
    from argos.data.providers.csv_provider import CsvProvider
    from tests import synthetic_tiingo

    rows, text = synthetic_tiingo.build(start=date(2015, 1, 2), end=date(2016, 12, 30), split_on=date(2015, 9, 1))
    series = tiingo.parse_raw(text, "sintético", date(2015, 1, 2), date(2016, 12, 30))
    (tmp_path / "X.csv").write_bytes(tiingo.render_converted(series))
    h = CsvProvider(tmp_path).get_price_history("X")
    closes = np.array([b.close for b in h.bars])
    mkt = Market(tuple(b.date for b in h.bars), {"X": np.array([b.open for b in h.bars])}, {"X": closes})
    run = simulate(mkt, [Execution(0, {"X": 1}, timing="close")], CostModel(0.0, 0.0), 100.0, 0, len(closes) - 1)

    # Ajuste hacia atrás multiplicativo (audit_corporate_actions en argos/data/audit.py): de t−1 a t la rentabilidad es
    #     P_t × split_t / (P_{t−1} − D_t)
    # con P sin ajustar y D el dividendo en efectivo con fecha ex t.
    tr = 1.0
    for prev, cur in zip(rows, rows[1:]):
        tr *= cur["close"] * cur["splitFactor"] / (prev["close"] - cur["divCash"])
    assert sum(r["divCash"] > 0 for r in rows) >= 7 and any(r["splitFactor"] != 1 for r in rows)
    assert run.final_value / 100 == pytest.approx(tr, rel=1e-6)
    # Comprobación aproximada: reinvertir cada dividendo al cierre de su fecha ex da casi lo mismo.
    shares = 1.0
    for cur in rows[1:]:
        shares *= cur["splitFactor"] * (1 + cur["divCash"] / cur["close"])
    assert run.final_value / 100 == pytest.approx(shares * rows[-1]["close"] / rows[0]["close"], rel=1e-3)
    # Sin dividendos ni split el resultado sería solo la variación de precio: los dividendos sí llegan al motor.
    assert run.final_value / 100 > rows[-1]["close"] * 2.0 / rows[0]["close"] * 1.01
