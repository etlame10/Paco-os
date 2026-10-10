"""Orquestador: une las capas en un análisis completo.

    datos → normalización → técnico → riesgo → (fundamental, noticias) → síntesis → explicación

Cada capa se inyecta, así que se puede sustituir cualquier pieza (otro
proveedor, otro explicador) sin tocar el resto.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from argos import __version__
from argos.analysis.fundamental.base import not_available_status as fundamental_status
from argos.analysis.news.base import not_available_status as news_status
from argos.analysis.synthesis import synthesize
from argos.analysis.technical.analyzer import TechnicalAnalyzer
from argos.analysis.technical.indicators import sma
from argos.core.models import AnalysisReport, ChartData, DataPoint
from argos.core.safety import LIVE_TRADING_ENABLED
from argos.data.base import DataProviderError
from argos.data.normalize import normalize_history, normalize_ticker
from argos.data.registry import ProviderRegistry, default_registry
from argos.explain.explainer import Explainer, TemplateExplainer
from argos.risk.engine import RiskEngine

MIN_BARS = 60
CHART_BARS = 250


class InsufficientDataError(DataProviderError):
    pass


class AnalysisService:
    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        technical: TechnicalAnalyzer | None = None,
        risk: RiskEngine | None = None,
        explainer: Explainer | None = None,
    ):
        self.registry = registry or default_registry()
        self.technical = technical or TechnicalAnalyzer()
        self.risk = risk or RiskEngine()
        self.explainer = explainer or TemplateExplainer()

    def analyze(self, raw_ticker: str) -> AnalysisReport:
        ticker = normalize_ticker(raw_ticker)
        provider = self.registry.resolve(ticker)
        asset = provider.get_asset_info(ticker)
        history = normalize_history(provider.get_price_history(ticker))
        df = history.to_dataframe()
        if len(df) < MIN_BARS:
            raise InsufficientDataError(
                f"{ticker}: solo hay {len(df)} sesiones válidas; se necesitan al menos {MIN_BARS}."
            )

        tech = self.technical.analyze(df)
        risk = self.risk.assess(df)
        conclusion = synthesize(tech.interpretations, risk)
        explanation = self.explainer.explain(asset, history.provenance, tech.interpretations, risk, conclusion)

        data = list(tech.data)
        for i, note in enumerate(history.normalization_notes):
            data.append(DataPoint(id=f"normalization_note_{i}", label="Nota de normalización", value=note))

        return AnalysisReport(
            ticker=ticker,
            generated_at=datetime.now(timezone.utc),
            argos_version=__version__,
            asset=asset,
            provenance=history.provenance,
            data=data,
            indicators=tech.indicators,
            interpretations=tech.interpretations,
            risk=risk,
            fundamental=fundamental_status(),
            news=news_status(),
            conclusion=conclusion,
            explanation=explanation,
            chart=_chart(df),
            live_trading_enabled=LIVE_TRADING_ENABLED,
        )


def _chart(df: pd.DataFrame) -> ChartData:
    close = df["close"]
    tail = slice(-CHART_BARS, None)

    def clean(s: pd.Series) -> list[float | None]:
        return [None if pd.isna(v) else round(float(v), 4) for v in s.iloc[tail]]

    return ChartData(
        dates=[d.date().isoformat() for d in df.index[tail]],
        close=[round(float(v), 4) for v in close.iloc[tail]],
        sma50=clean(sma(close, 50)),
        sma200=clean(sma(close, 200)),
    )
