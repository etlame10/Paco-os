"""Auditoría de datos y calendario NYSE, con casos extremos SINTÉTICOS.

Cada test fija un comportamiento: la auditoría debe FALLAR o AVISAR cuando los datos
son inválidos o se interpretan mal, y pasar con datos sintéticos correctos.
Nada de esto dice nada sobre rentabilidad.
"""

from datetime import date, datetime, timezone

import pytest

from argos.data import audit
from argos.data.calendar_us import holidays, non_session_reason, sessions
from argos.data.quality import assess_quality
from argos.data.providers.csv_provider import CsvProvider
from argos.data.sources import tiingo
from tests import synthetic_tiingo as syn

KEY = "k" * 40
NOW = lambda: datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731
PERIOD = (date(2007, 1, 3), date(2025, 12, 31))


def fetch_of(text):
    return lambda url, headers: (200, {}, text.encode())


def pipeline(tmp_path, text, ticker="KO"):
    raw, csvd = tmp_path / "raw", tmp_path / "csv"
    tiingo.download_ticker(ticker, date(2007, 1, 1), date(2025, 12, 31), key=KEY, raw_dir=raw, fetch=fetch_of(text), now=NOW)
    tiingo.convert(ticker, raw_dir=raw, csv_dir=csvd)
    return raw, csvd


def run_audit(raw, csvd, ticker="KO"):
    a = audit.audit_csv(ticker, csvd / f"{ticker}.csv", PERIOD)
    if a.rows:
        audit.audit_provenance(a, raw)
    return a, {c.id: c for c in a.checks}


@pytest.fixture(scope="module")
def clean():
    return syn.build()


# ----------------------------------------------------------------- calendario NYSE


def test_calendar_matches_validated_reference_counts():
    """Recuentos por año validados contra pandas_market_calendars 5.5.0 (ver informe de auditoría)."""
    expected = {2007: 251, 2008: 253, 2009: 252, 2010: 252, 2011: 252, 2012: 250, 2013: 252, 2014: 252,
                2015: 252, 2016: 252, 2017: 251, 2018: 251, 2019: 252, 2020: 253, 2021: 252, 2022: 251,
                2023: 250, 2024: 252, 2025: 250}
    for y, n in expected.items():
        assert len(sessions(date(y, 1, 1), date(y, 12, 31))) == n, y
    assert len(sessions(*PERIOD)) == 4780  # = filas de cada descarga real según el usuario


@pytest.mark.parametrize("d, reason", [
    (date(2007, 1, 2), "Gerald Ford"), (date(2012, 10, 29), "Sandy"), (date(2018, 12, 5), "Bush"),
    (date(2025, 1, 9), "Carter"), (date(2022, 6, 20), "Juneteenth"), (date(2021, 12, 24), "Navidad"),
    (date(2016, 3, 25), "Viernes Santo"), (date(2024, 11, 28), "Acción de Gracias"),
])
def test_known_closures(d, reason):
    assert reason in non_session_reason(d)


def test_saturday_new_year_does_not_close_previous_friday():
    assert non_session_reason(date(2021, 12, 31)) is None  # 1-1-2022 fue sábado
    assert date(2021, 12, 31) not in holidays(2021) and date(2021, 12, 31) not in holidays(2022)
    assert non_session_reason(date(2023, 1, 2)) == "Año Nuevo"  # 1-1-2023 fue domingo


# ----------------------------------------------------------------- caso limpio


def test_clean_synthetic_dataset_passes_every_check(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    a, c = run_audit(raw, csvd)
    pending = [x.id for x in a.checks if x.status != audit.OK]
    assert pending == ["eventos"], [(x.id, x.status, x.detail) for x in a.checks if x.status != audit.OK]
    assert c["eventos"].status == audit.NA and a.status == audit.WARN  # nunca "OK" sin verificación externa
    assert a.rows == 4780
    assert "2014-06-09 ×2.0" in c["eventos"].detail  # el split declarado aparece
    assert "2015:4" in c["eventos"].detail
    assert c["conversion"].status == audit.OK and c["ajustes"].status == audit.OK


def test_adjusted_series_hides_split_but_events_reveal_it(tmp_path, clean):
    """Clave del caso 'ningún split detectado': en la serie AJUSTADA no hay salto,
    pero el split existe y lo declara splitFactor."""
    raw, csvd = pipeline(tmp_path, clean[1])
    h = CsvProvider(csvd).get_price_history("KO")
    q = {c.id: c for c in assess_quality(h).checks}
    assert q["splits"].status == "ok"  # no ve el split… porque está ajustado
    assert "NO significa que no hubiera splits" in q["splits"].detail
    _, c = run_audit(raw, csvd)
    assert "2014-06-09" in c["eventos"].detail


def test_unadjusted_prices_would_create_false_crash(clean):
    """Con precios SIN ajustar, el split aparece como una caída del ~50 % y el control lo bloquea."""
    from argos.core.models import Bar, PriceHistory, Provenance

    rows = clean[0]
    bars = [Bar(date=r["date"], open=r["open"], high=r["high"], low=r["low"], close=r["close"], volume=r["volume"])
            for r in rows]
    h = PriceHistory(ticker="KO", bars=bars, provenance=Provenance(
        provider="t", source_description="t", is_simulated=False, retrieved_at=NOW()))
    q = {c.id: c for c in assess_quality(h).checks}
    assert q["splits"].status == "bloqueo" and "2014-06-09" in q["splits"].examples[0]


# ----------------------------------------------------------------- ajustes corporativos incoherentes


def mutate(rows, fn):
    rows = [dict(r) for r in rows]
    fn(rows)
    return syn.render(rows)


def test_adjustment_without_declared_event_fails(tmp_path, clean):
    def hidden(rows):  # el factor cambia en 2010-05-03 sin dividendo ni split declarados
        for r in rows:
            if r["date"] < date(2010, 5, 3):
                r["f"] *= 0.98
    raw, csvd = pipeline(tmp_path, mutate(clean[0], hidden))
    _, c = run_audit(raw, csvd)
    assert c["ajustes"].status == audit.FAIL and "sin evento" in c["ajustes"].examples[0]


def test_declared_dividend_without_adjustment_fails(tmp_path, clean):
    def ghost(rows):
        target = next(r for r in rows if r["date"] == date(2011, 8, 1))
        target["divCash"] = 0.5  # se declara, pero el factor no cambia
    raw, csvd = pipeline(tmp_path, mutate(clean[0], ghost))
    _, c = run_audit(raw, csvd)
    assert c["ajustes"].status == audit.FAIL and "2011-08-01" in " ".join(c["ajustes"].examples)


def test_wrong_split_factor_fails(tmp_path, clean):
    def wrong(rows):
        next(r for r in rows if r["date"] == date(2014, 6, 9))["splitFactor"] = 3.0
    raw, csvd = pipeline(tmp_path, mutate(clean[0], wrong))
    _, c = run_audit(raw, csvd)
    assert c["ajustes"].status == audit.FAIL


def test_undeclared_split_is_flagged(tmp_path):
    """Split que el proveedor NO declara ni ajusta: salto en la serie ajustada y en la original."""
    rows, _ = syn.build(split_on=None, seed=11)
    for r in rows:
        if r["date"] >= date(2015, 3, 2):
            for k in ("open", "high", "low", "close"):
                r[k] = round(r[k] / 2, 2)
    text = syn.render(rows)
    raw, csvd = pipeline(tmp_path, text)
    a, c = run_audit(raw, csvd)
    assert c["saltos"].status == audit.FAIL and "proporción de split" in c["saltos"].detail
    assert c["splits_no_declarados"].status == audit.WARN and "2015-03-02" in c["splits_no_declarados"].examples[0]


# ----------------------------------------------------------------- calendario, valores, procedencia


def test_missing_session_and_holiday_row_are_flagged(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    p = csvd / "KO.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines = [x for x in lines if not x.startswith("2013-07-15")]  # falta una sesión real
    lines.insert(1, "2007-01-02,1,1,1,1,1")  # día de luto (no hubo sesión)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _, c = run_audit(raw, csvd)
    ex = " ".join(c["calendario"].examples)
    assert c["calendario"].status == audit.FAIL and "falta 2013-07-15" in ex and "Gerald Ford" in ex
    assert c["orden"].status == audit.OK  # 2007-01-02 va antes de 2007-01-03: el orden es correcto


@pytest.mark.parametrize("bad_row, fragment", [
    ("2013-07-15,,1,1,1,1", "valor vacío"),
    ("2013-07-15,abc,1,1,1,1", "valor vacío o no numérico"),
    ("2013-07-15,-1,1,1,1,1", "precio ≤ 0"),
    ("2013-07-15,nan,1,1,1,1", "valor vacío o no numérico"),
    ("2013-07-15,1,1,1", "campos"),
    ("15/07/2013,1,1,1,1,1", "fecha"),
], ids=["vacio", "texto", "negativo", "nan", "cortada", "fecha"])
def test_invalid_values_are_reported(tmp_path, clean, bad_row, fragment):
    raw, csvd = pipeline(tmp_path, clean[1])
    p = csvd / "KO.csv"
    p.write_text("\n".join(bad_row if x.startswith("2013-07-15") else x for x in p.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
    _, c = run_audit(raw, csvd)
    assert c["valores"].status == audit.FAIL and fragment in " ".join(c["valores"].examples)
    assert c["procedencia"].status == audit.FAIL  # además, el CSV ya no es el convertido


def test_duplicate_and_stale_rows(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    p = csvd / "KO.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith("2016-02-01"))
    vals = lines[i].split(",")[1:]
    for k in range(1, 6):
        d = lines[i + k].split(",")[0]
        lines[i + k] = ",".join([d, *vals])
    lines.insert(i, lines[i])  # duplicado
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _, c = run_audit(raw, csvd)
    assert c["orden"].status == audit.FAIL and "2016-02-01" in c["orden"].examples
    assert c["repetidos"].status == audit.WARN


def test_truncated_history_is_flagged(tmp_path):
    rows, text = syn.build(start=date(2010, 1, 4))
    raw, csvd = pipeline(tmp_path, text)
    _, c = run_audit(raw, csvd)
    assert c["calendario"].status == audit.FAIL and "falta 2007-01-03" in c["calendario"].examples[0]


def test_symbol_change_or_copied_file_is_flagged(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    src = csvd / "KO.source.txt"
    src.write_text(src.read_text(encoding="utf-8").replace("Ticker: KO", "Ticker: XOM"), encoding="utf-8")
    _, c = run_audit(raw, csvd)
    assert c["procedencia"].status == audit.FAIL and "XOM" in c["procedencia"].detail


def test_missing_provenance_is_flagged(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    (csvd / "KO.source.txt").unlink()
    a, c = run_audit(raw, csvd)
    assert c["procedencia"].status == audit.FAIL and a.status == audit.FAIL


def test_modified_original_is_flagged(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    f = next(raw.glob("KO_*.csv"))
    f.write_text(f.read_text(encoding="utf-8").replace(",0.3,1.0", ",0.31,1.0", 1), encoding="utf-8")
    _, c = run_audit(raw, csvd)
    assert c["original"].status == audit.FAIL


def test_without_original_corporate_actions_are_not_claimed(tmp_path, clean):
    raw, csvd = pipeline(tmp_path, clean[1])
    for f in raw.iterdir():
        f.unlink()
    a, c = run_audit(raw, csvd)
    assert c["original"].status == audit.NA and "ajustes" not in c
    assert a.status == audit.WARN  # nunca "OK" si algo no se pudo comprobar


def test_cli_report_and_exit_codes(tmp_path, clean, capsys):
    raw, csvd = pipeline(tmp_path, clean[1])
    out = tmp_path / "informe.md"
    code = audit.main(["KO", "--csv-dir", str(csvd), "--raw-dir", str(raw), "--salida", str(out)])
    text = out.read_text(encoding="utf-8")
    assert code == 0 and "| Limitación |" in text and "SHA-256" in text
    assert audit.main(["SPY", "--csv-dir", str(csvd), "--raw-dir", str(raw)]) == 2  # falta el fichero
    (csvd / "KO.source.txt").unlink()
    assert audit.main(["KO", "--csv-dir", str(csvd), "--raw-dir", str(raw)]) == 1


def test_edited_csv_with_forged_provenance_is_caught_by_reconversion(tmp_path, clean):
    """Alguien edita un precio Y actualiza la huella del .source.txt para disimularlo:
    la procedencia parece coherente, pero rehacer la conversión desde el original lo delata."""
    import hashlib

    raw, csvd = pipeline(tmp_path, clean[1])
    p, src = csvd / "KO.csv", csvd / "KO.source.txt"
    old_sha = hashlib.sha256(p.read_bytes()).hexdigest()
    lines = p.read_text(encoding="utf-8").splitlines()
    parts = lines[500].split(",")
    parts[4] = f"{float(parts[4]) * 1.01:.6f}"  # cierre +1 % (sigue siendo coherente con su máximo/mínimo)
    parts[2] = f"{max(float(parts[2]), float(parts[4])):.6f}"
    lines[500] = ",".join(parts)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    src.write_text(src.read_text(encoding="utf-8").replace(old_sha, hashlib.sha256(p.read_bytes()).hexdigest()), encoding="utf-8")
    _, c = run_audit(raw, csvd)
    assert c["procedencia"].status == audit.OK  # la falsificación pasa este control…
    assert c["conversion"].status == audit.FAIL  # …pero no el de reconversión
