import math

import pytest

from argos.analysis.synthesis import AREA_WEIGHTS, synthesize
from argos.analysis.technical.analyzer import TechnicalAnalyzer
from argos.core.models import Interpretation, Layer, RiskAssessment, Stance
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry
from argos.pipeline import AnalysisService, InsufficientDataError
from argos.risk.engine import RiskEngine, risk_level
from tests.conftest import make_df


@pytest.fixture(scope="module")
def service():
    return AnalysisService(registry=ProviderRegistry([DemoProvider()]))


@pytest.fixture(scope="module")
def report(service):
    return service.analyze("demo-alcista")


def test_report_has_every_section(report):
    assert report.ticker == "DEMO-ALCISTA"
    assert report.data and report.indicators and report.interpretations
    assert report.risk.metrics and report.risk.scenarios
    assert report.conclusion.label and report.conclusion.factors
    titles = [s.title for s in report.explanation.sections]
    for t in ["Situación", "Análisis técnico", "Riesgo", "Conclusión", "Por qué", "Qué NO sabemos"]:
        assert t in titles
    assert len(report.chart.close) == len(report.chart.dates) == len(report.chart.sma50)


def test_layers_are_labelled_correctly(report):
    assert all(d.layer is Layer.DATA for d in report.data)
    assert all(i.layer is Layer.INDICATOR for i in report.indicators + report.risk.metrics)
    assert all(i.layer is Layer.INTERPRETATION for i in report.interpretations + report.risk.interpretations)
    assert report.conclusion.layer is Layer.CONCLUSION


def test_every_interpretation_is_auditable(report):
    known = {d.id for d in report.data} | {i.id for i in report.indicators} | {m.id for m in report.risk.metrics}
    for i in report.interpretations + report.risk.interpretations:
        assert i.rule, i.id
        assert i.evidence, i.id
        assert set(i.evidence) <= known, f"{i.id} cita evidencia inexistente"


def test_conclusion_factors_trace_back_to_interpretations(report):
    ids = {i.id for i in report.interpretations}
    total_w = sum(f.weight for f in report.conclusion.factors)
    assert all(f.interpretation_id in ids for f in report.conclusion.factors)
    assert report.conclusion.score == pytest.approx(
        sum(f.contribution for f in report.conclusion.factors) / total_w, abs=1e-3
    )
    assert "garantiza" in report.conclusion.disclaimer


def test_simulated_flag_propagates_everywhere(report):
    assert report.provenance.is_simulated is True
    assert "SIMULADOS" in report.provenance.warning
    assert "SIMULADOS" in report.explanation.sections[0].text
    assert report.live_trading_enabled is False


def test_demo_profiles_produce_expected_direction(service):
    assert service.analyze("DEMO-ALCISTA").conclusion.stance is Stance.BULLISH
    assert service.analyze("DEMO-BAJISTA").conclusion.stance is Stance.BEARISH
    assert service.analyze("DEMO-VOLATIL").risk.level in ("elevado", "muy elevado")


def test_steady_uptrend_is_bullish_on_trend_factors():
    closes = [100 * (1.002 ** i) * (1 + 0.01 * math.sin(i)) for i in range(300)]
    tech = TechnicalAnalyzer().analyze(make_df(closes))
    trend = [i for i in tech.interpretations if i.area == "tendencia"]
    assert len(trend) == 3 and all(i.stance is Stance.BULLISH for i in trend)


def test_short_history_skips_long_indicators_instead_of_inventing():
    tech = TechnicalAnalyzer().analyze(make_df([100.0 + i for i in range(80)]))
    by_id = {i.id: i for i in tech.indicators}
    assert by_id["sma200"].value is None
    assert by_id["ret_1y"].value is None
    assert not any(i.id == "trend_price_sma200" for i in tech.interpretations)


def test_insufficient_data_raises():
    class Tiny(DemoProvider):
        def get_price_history(self, ticker, start=None, end=None):
            h = super().get_price_history(ticker)
            return h.model_copy(update={"bars": h.bars[:10]})

    with pytest.raises(InsufficientDataError):
        AnalysisService(registry=ProviderRegistry([Tiny()])).analyze("DEMO-ALCISTA")


def test_risk_levels_and_scenarios():
    assert risk_level(0.10) == "bajo"
    assert risk_level(0.30) == "moderado"
    assert risk_level(0.45) == "elevado"
    assert risk_level(0.90) == "muy elevado"
    assert risk_level(None) == "desconocido"
    df = make_df([100 * (1 + 0.02 * math.sin(i)) for i in range(300)])
    risk = RiskEngine().assess(df)
    one, two = risk.scenarios
    assert two.low < one.low < df["close"].iloc[-1] < one.high < two.high
    assert all("No es una predicción" in s.basis for s in risk.scenarios)


def test_synthesis_with_mixed_factors_is_transparent():
    def mk(i, area, stance):
        return Interpretation(id=i, area=area, statement=i, stance=stance, rule="r", evidence=["x"])

    interps = [
        mk("a", "tendencia", Stance.BULLISH),
        mk("b", "momentum", Stance.BEARISH),
        mk("c", "volumen", Stance.NEUTRAL),
        mk("d", "soportes y resistencias", Stance.NEUTRAL),  # no direccional: no entra
    ]
    risk = RiskAssessment(level="elevado", metrics=[], interpretations=[], scenarios=[])
    c = synthesize(interps, risk)
    assert [f.interpretation_id for f in c.factors] == ["a", "b", "c"]
    assert c.score == 0.0
    assert c.stance is Stance.NEUTRAL
    assert "poco sólida" in c.agreement_note
    assert "riesgo elevado" in c.summary
    assert set(AREA_WEIGHTS) == {"tendencia", "momentum", "volumen"}


def test_synthesis_without_factors():
    risk = RiskAssessment(level="bajo", metrics=[], interpretations=[], scenarios=[])
    assert "Sin conclusión" in synthesize([], risk).label
