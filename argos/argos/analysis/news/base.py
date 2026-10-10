"""Noticias y contexto de mercado — interfaz preparada, sin implementar.

Un futuro `NewsProvider` devolverá `NewsItem` con fuente, fecha y URL. Toda
noticia deberá conservar su fuente original para que la interpretación
(sentimiento, relevancia) se distinga siempre del hecho (el titular).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from argos.core.models import SectionStatus


class NewsItem(BaseModel):
    ticker: str
    published_at: datetime
    title: str
    source: str
    url: str | None = None


class NewsProvider(ABC):
    name: str

    @abstractmethod
    def get_news(self, ticker: str, limit: int = 20) -> list[NewsItem]: ...


def not_available_status() -> SectionStatus:
    return SectionStatus(
        available=False,
        note="Noticias y contexto de mercado aún no implementados: no hay fuente de noticias conectada.",
    )
