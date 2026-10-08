"""Formato CSV: el lector es estricto y nunca rellena ni corrige datos en silencio."""

from datetime import date, timedelta

import pytest

from argos.data.normalize import normalize_history
from argos.data.providers.csv_provider import CsvFormatError, CsvProvider

H = "date,open,high,low,close,volume\n"


def load(tmp_path, content, name="TEST"):
    (tmp_path / f"{name}.csv").write_text(content, encoding="utf-8")
    return CsvProvider(tmp_path).get_price_history(name)


def daily_rows(n=5, start=date(2024, 1, 1)):
    rows, d = [], start
    while len(rows) < n:
        if d.weekday() < 5:
            rows.append(f"{d.isoformat()},10,11,9,10.5,100")
        d += timedelta(days=1)
    return "\n".join(rows) + "\n"


def test_valid_file_with_extra_columns_and_uppercase_header(tmp_path):
    content = "Date,Open,High,Low,Close,Adj Close,Volume\n2024-01-02,10,11,9,10.5,10.4,100\n2024-01-03,10.5,12,10,11,10.9,200\n"
    h = load(tmp_path, content)
    assert [b.close for b in h.bars] == [10.5, 11.0]  # usa close, ignora Adj Close
    assert h.provenance.is_simulated is False


def test_midnight_timestamp_is_accepted(tmp_path):
    assert len(load(tmp_path, H + "2024-01-02 00:00:00,10,11,9,10,1\n").bars) == 1


@pytest.mark.parametrize(
    "row, fragment",
    [
        ("02/01/2024,10,11,9,10,1", "AAAA-MM-DD"),
        ("2024-13-01,10,11,9,10,1", "no existe"),
        ("2024-02-30,10,11,9,10,1", "no existe"),
        ("1850-01-02,10,11,9,10,1", "1900"),
        (f"{(date.today() + timedelta(days=30)).isoformat()},10,11,9,10,1", "futuro"),
        ("2024-01-02 09:30,10,11,9,10,1", "intradía"),
        ("2024-01-02,,11,9,10,1", "vacío"),
        ("2024-01-02,10,11,9,10,", "0 explícitamente"),
        ('2024-01-02,"10,5",11,9,10,1', "punto como separador decimal"),
        ("2024-01-02,abc,11,9,10,1", "no es un número"),
        ("2024-01-02,nan,11,9,10,1", "finito"),
        ("2024-01-02,inf,11,9,10,1", "finito"),
    ],
)
def test_invalid_rows_are_rejected_with_line_number(tmp_path, row, fragment):
    with pytest.raises(CsvFormatError) as exc:
        load(tmp_path, H + "2024-01-01,10,11,9,10,1\n" + row + "\n")
    assert fragment in str(exc.value)
    assert "línea 3" in str(exc.value)


def test_duplicate_dates_rejected(tmp_path):
    with pytest.raises(CsvFormatError, match="ya aparece en la línea 2"):
        load(tmp_path, H + "2024-01-02,10,11,9,10,1\n2024-01-02,10,11,9,10,1\n")


def test_intraday_file_rejected(tmp_path):
    with pytest.raises(CsvFormatError, match="DIARIOS"):
        load(tmp_path, H + "2024-01-02 09:30,10,11,9,10,1\n2024-01-02 16:00,10,11,9,10.5,1\n")


def test_weekly_file_rejected(tmp_path):
    rows = "".join(f"2024-{m:02d}-{d:02d},10,11,9,10,1\n" for m in (1, 2, 3) for d in (1, 8, 15, 22))
    with pytest.raises(CsvFormatError, match="semanal o mensual"):
        load(tmp_path, H + rows)


def test_crypto_style_every_day_is_accepted(tmp_path):
    rows = "".join(f"2024-01-{d:02d},10,11,9,10,1\n" for d in range(1, 29))
    assert len(load(tmp_path, H + rows).bars) == 28


def test_empty_file_rejected(tmp_path):
    with pytest.raises(CsvFormatError, match="ninguna fila"):
        load(tmp_path, H)


def test_semicolon_separator_rejected_with_hint(tmp_path):
    with pytest.raises(CsvFormatError, match="coma"):
        load(tmp_path, "date;open;high;low;close;volume\n2024-01-02;10;11;9;10;1\n")


def test_missing_columns(tmp_path):
    with pytest.raises(CsvFormatError, match="faltan columnas"):
        load(tmp_path, "date,close\n2024-01-02,10\n")


def test_unsorted_rows_are_sorted_not_rejected(tmp_path):
    h = normalize_history(load(tmp_path, H + "2024-01-03,10,11,9,10,1\n2024-01-02,10,11,9,10,1\n"))
    assert [b.date for b in h.bars] == [date(2024, 1, 2), date(2024, 1, 3)]


def test_incoherent_bar_dropped_and_noted(tmp_path):
    h = normalize_history(load(tmp_path, H + daily_rows(3) + "2024-01-04,10,9,8,10,1\n"))
    assert len(h.bars) == 3
    assert any("descartada" in n for n in h.normalization_notes)


def test_suspicious_jump_is_noted_not_corrected(tmp_path):
    h = normalize_history(load(tmp_path, H + "2024-01-02,100,101,99,100,1\n2024-01-03,25,26,24,25,1\n"))
    assert h.bars[1].close == 25  # no se toca
    assert any("split" in n for n in h.normalization_notes)


def test_demo_prefixed_csv_is_always_simulated(tmp_path):
    h = load(tmp_path, H + daily_rows(3), name="DEMO-PRUEBA")
    assert h.provenance.is_simulated is True
    assert "SIMULADOS" in h.provenance.warning
