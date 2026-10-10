"""Contrato que debe cumplir cualquier fuente de datos de mercado.

Para añadir un proveedor nuevo (Yahoo, Alpha Vantage, Polygon, un CSV, una base
de datos...) basta con implementar esta clase y registrarla en el
`ProviderRegistry`. El resto de ARGOS solo conoce esta interfaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from argos.core.models import AssetInfo, PriceHistory


class DataProviderError(Exception):
    pass


class TickerNotFoundError(DataProviderError):
    pass


class MarketDataProvider(ABC):
    #: Identificador corto y estable del proveedor.
    name: str
    #: True si el proveedor genera datos que NO son de mercado real.
    is_simulated: bool

    @abstractmethod
    def supports(self, ticker: str) -> bool:
        """¿Puede este proveedor servir datos para este ticker?"""

    @abstractmethod
    def get_asset_info(self, ticker: str) -> AssetInfo: ...

    @abstractmethod
    def get_price_history(
        self, ticker: str, start: date | None = None, end: date | None = None
    ) -> PriceHistory:
        """Histórico diario OHLCV, ordenado por fecha ascendente."""

    def list_tickers(self) -> list[str] | None:
        """Tickers conocidos, si el proveedor puede enumerarlos."""
        return None

    def describe(self) -> dict:
        return {"name": self.name, "is_simulated": self.is_simulated}
