from datetime import date, datetime, timezone

import pytest

from argos.core.models import Bar, PriceHistory, Provenance
from argos.data.base import DataProviderError, TickerNotFoundError
from argos.data.normalize import normalize_history, normalize_ticker
from argos.data.providers.csv_provider import CsvProvider
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry


def _prov():
    return Provenance(provider="t", source_description="t", is_simulated=False, retrieved_at=datetime.now(timezone.utc))


def test_normalize_ticker():
    assert normalize_ticker("  aapl ") == "AAPL"
    assert normalize_ticker("demo-alcista") == "DEMO-ALCISTA"
    assert normalize_ticker("brk.b") == "BRK.B"
    for bad in ["", "   ", "AA PL", "../etc", "<script>", "A" * 30]:
        with pytest.raises(ValueError):
            normalize_ticker(bad)


def test_normalize_history_sorts_dedupes_and_drops_invalid_without_inventing():
    good = dict(open=10, high=11, low=9, close=10.5, volume=100)
    bars = [
        Bar(date=date(2024, 1, 3), **good),
        Bar(date=date(2024, 1, 2), **good),
        Bar(date=date(2024, 1, 2), **{**good, "close": 10.2}),  # duplicado
        Bar(date=date(2024, 1, 4), **{**good, "close": -1}),  # inválido
        Bar(date=date(2024, 1, 5), **{**good, "high": 9.5}),  # máximo incoherente
    ]
    out = normalize_history(PriceHistory(ticker="X", bars=bars, provenance=_prov()))
    assert [b.date for b in out.bars] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert out.bars[0].close == 10.2
    assert len(out.normalization_notes) == 3


def test_demo_provider_is_flagged_and_deterministic():
    p = DemoProvider()
    assert p.is_simulated is True
    a = p.get_price_history("DEMO-ALCISTA")
    b = p.get_price_history("DEMO-ALCISTA")
    assert a.provenance.is_simulated is True
    assert "SIMULADOS" in a.provenance.warning
    assert [x.close for x in a.bars] == [x.close for x in b.bars]
    assert "ficticia" in p.get_asset_info("DEMO-ALCISTA").name
    assert all(t.startswith("DEMO-") for t in p.list_tickers())


def test_demo_provider_never_serves_real_tickers():
    p = DemoProvider()
    for real in ["AAPL", "MSFT", "SPY", "BTC-USD"]:
        assert not p.supports(real)
        with pytest.raises(TickerNotFoundError):
            p.get_price_history(real)


def test_demo_data_ends_in_the_past_not_live():
    bars = DemoProvider().get_price_history("DEMO-LATERAL").bars
    assert bars[-1].date < date.today()


def test_csv_provider_reads_real_file(tmp_path):
    (tmp_path / "TEST.csv").write_text(
        "Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,100\n2024-01-03,10.5,12,10,11,200\n"
    )
    p = CsvProvider(tmp_path)
    assert p.supports("TEST") and not p.supports("OTHER")
    assert p.list_tickers() == ["TEST"]
    h = p.get_price_history("TEST")
    assert h.provenance.is_simulated is False
    assert [b.close for b in h.bars] == [10.5, 11.0]


def test_csv_provider_rejects_bad_columns(tmp_path):
    (tmp_path / "BAD.csv").write_text("date,close\n2024-01-02,10\n")
    with pytest.raises(DataProviderError):
        CsvProvider(tmp_path).get_price_history("BAD")


def test_registry_resolution_order_and_honest_error(tmp_path):
    (tmp_path / "DEMO-ALCISTA.csv").write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,1,1\n")
    reg = ProviderRegistry([CsvProvider(tmp_path), DemoProvider()])
    assert reg.resolve("DEMO-ALCISTA").name == "csv"  # el primero registrado gana
    with pytest.raises(TickerNotFoundError) as exc:
        reg.resolve("AAPL")
    assert "no se inventa" in str(exc.value)
    assert "DEMO-ALCISTA" in str(exc.value)
