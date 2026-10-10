"""Análisis fundamental — interfaz preparada, sin implementar en la fase 1.

Un futuro `FundamentalDataProvider` (resultados, balance, valoración, deuda,
crecimiento...) alimentará a un `FundamentalAnalyzer` que devolverá
`IndicatorValue` (ratios: PER, deuda/EBITDA, crecimiento de ventas...) e
`Interpretation`, igual que el análisis técnico, para que la síntesis y la
explicación los traten exactamente igual.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from argos.core.models import IndicatorValue, Interpretation, SectionStatus


class FundamentalDataProvider(ABC):
    name: str
    is_simulated: bool

    @abstractmethod
    def get_financials(self, ticker: str) -> dict:
        """Estados financieros normalizados (cuenta de resultados, balance, flujos)."""


class FundamentalAnalyzer(ABC):
    @abstractmethod
    def analyze(self, ticker: str) -> tuple[list[IndicatorValue], list[Interpretation]]: ...


def not_available_status() -> SectionStatus:
    return SectionStatus(
        available=False,
        note=(
            "Análisis fundamental aún no implementado: no hay fuente de datos "
            "financieros conectada. ARGOS no muestra ratios inventados."
        ),
    )
