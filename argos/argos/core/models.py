"""Modelos de dominio compartidos por todas las capas de ARGOS.

Principio central: todo lo que ARGOS produce pertenece a una de cuatro capas
(`Layer`) y se etiqueta como tal, para no confundir nunca una interpretación
con un hecho:

    DATO            -> lo que realmente sabemos (precios, volumen, fechas).
    INDICADOR       -> lo que calculamos a partir de los datos (SMA, RSI...).
    INTERPRETACIÓN  -> lo que creemos que significan los indicadores.
    CONCLUSIÓN      -> la evaluación final, que agrega interpretaciones.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Layer(str, Enum):
    DATA = "dato"
    INDICATOR = "indicador"
    INTERPRETATION = "interpretacion"
    CONCLUSION = "conclusion"


class Stance(str, Enum):
    """Sesgo de una interpretación. No es una orden ni una predicción."""

    BULLISH = "alcista"
    BEARISH = "bajista"
    NEUTRAL = "neutral"


# --------------------------------------------------------------------------- datos


class Provenance(BaseModel):
    """De dónde salen los datos. Viaja con cada análisis hasta la interfaz."""

    provider: str
    source_description: str
    is_simulated: bool
    retrieved_at: datetime
    warning: str | None = None


class Bar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float


class AssetInfo(BaseModel):
    ticker: str
    name: str
    currency: str = "USD"
    exchange: str | None = None
    asset_type: str = "acción"
    description: str | None = None


class PriceHistory(BaseModel):
    ticker: str
    bars: list[Bar]
    provenance: Provenance
    normalization_notes: list[str] = Field(default_factory=list)

    def to_dataframe(self):
        import pandas as pd

        df = pd.DataFrame([b.model_dump() for b in self.bars])
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date").sort_index()


# ------------------------------------------------------------------ resultados


class DataPoint(BaseModel):
    """Un hecho observado directamente en los datos."""

    id: str
    label: str
    value: Any
    unit: str | None = None
    layer: Layer = Layer.DATA


class IndicatorValue(BaseModel):
    """Un valor calculado. `method` explica cómo se calcula."""

    id: str
    name: str
    value: float | None
    unit: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    method: str
    layer: Layer = Layer.INDICATOR


class Interpretation(BaseModel):
    """Lo que ARGOS cree que significa un conjunto de indicadores.

    `rule` describe la regla aplicada en lenguaje llano y `evidence` lista los
    ids de los indicadores usados, para que cualquier interpretación pueda
    auditarse hasta los números de los que sale.
    """

    id: str
    area: str
    statement: str
    stance: Stance
    rule: str
    evidence: list[str]
    caveat: str | None = None
    layer: Layer = Layer.INTERPRETATION


class Scenario(BaseModel):
    name: str
    description: str
    low: float
    high: float
    basis: str


class RiskAssessment(BaseModel):
    level: str
    metrics: list[IndicatorValue]
    interpretations: list[Interpretation]
    scenarios: list[Scenario]


class Factor(BaseModel):
    """Contribución visible de una interpretación a la conclusión."""

    interpretation_id: str
    area: str
    statement: str
    stance: Stance
    weight: float
    contribution: float


class Conclusion(BaseModel):
    label: str
    stance: Stance
    summary: str
    score: float
    score_method: str
    factors: list[Factor]
    risk_level: str
    agreement_note: str
    disclaimer: str
    layer: Layer = Layer.CONCLUSION


class SectionStatus(BaseModel):
    """Estado de una sección que todavía no está implementada o no tiene datos."""

    available: bool
    note: str


class ExplanationSection(BaseModel):
    title: str
    text: str


class Explanation(BaseModel):
    generator: str
    method_note: str
    sections: list[ExplanationSection]


class ChartData(BaseModel):
    dates: list[str]
    close: list[float]
    sma50: list[float | None]
    sma200: list[float | None]


class AnalysisReport(BaseModel):
    ticker: str
    generated_at: datetime
    argos_version: str
    asset: AssetInfo
    provenance: Provenance
    data: list[DataPoint]
    indicators: list[IndicatorValue]
    interpretations: list[Interpretation]
    risk: RiskAssessment
    fundamental: SectionStatus
    news: SectionStatus
    conclusion: Conclusion
    explanation: Explanation
    chart: ChartData
    live_trading_enabled: bool = False
