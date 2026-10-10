"""Registro de proveedores: decide qué fuente sirve cada ticker."""

from __future__ import annotations

from argos.data.base import MarketDataProvider, TickerNotFoundError


class ProviderRegistry:
    def __init__(self, providers: list[MarketDataProvider] | None = None):
        self._providers: list[MarketDataProvider] = list(providers or [])

    def register(self, provider: MarketDataProvider, *, priority: bool = False) -> None:
        if priority:
            self._providers.insert(0, provider)
        else:
            self._providers.append(provider)

    @property
    def providers(self) -> list[MarketDataProvider]:
        return list(self._providers)

    def resolve(self, ticker: str) -> MarketDataProvider:
        """Primer proveedor (por orden de registro) que soporta el ticker."""
        for provider in self._providers:
            if provider.supports(ticker):
                return provider
        demo = [
            t
            for p in self._providers
            if p.is_simulated
            for t in (p.list_tickers() or [])
        ]
        hint = f" Tickers de demostración disponibles: {', '.join(demo)}." if demo else ""
        raise TickerNotFoundError(
            f"Ningún proveedor de datos configurado tiene datos para {ticker}. "
            "ARGOS no se inventa datos de activos reales." + hint
        )


def default_registry() -> ProviderRegistry:
    """Configuración por defecto: CSV locales (datos reales importados) y demo."""
    from argos.data.providers.csv_provider import CsvProvider
    from argos.data.providers.demo import DemoProvider

    return ProviderRegistry([CsvProvider(), DemoProvider()])
