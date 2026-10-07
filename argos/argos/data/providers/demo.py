"""Proveedor de DATOS SIMULADOS para desarrollo y pruebas.

- Solo sirve tickers ficticios con prefijo `DEMO-`, para que nunca se puedan
  confundir con un activo real (no genera datos falsos de AAPL, por ejemplo).
- Es determinista: el mismo ticker produce siempre la misma serie, lo que
  permite tests reproducibles.
- Las fechas terminan en una fecha fija del pasado: no aparenta ser "en vivo".
"""

from __future__ import annotations

import math
import random
import zlib
from datetime import date, datetime, timedelta, timezone

from argos.core.models import AssetInfo, Bar, PriceHistory, Provenance
from argos.data.base import MarketDataProvider, TickerNotFoundError

DEMO_WARNING = (
    "DATOS SIMULADOS DE DEMOSTRACIÓN. Serie generada por ordenador para un "
    "activo ficticio. No representa ningún mercado real."
)

# (nombre, deriva diaria, volatilidad diaria, reversión a la media)
_PROFILES: dict[str, tuple[str, float, float, float]] = {
    "DEMO-ALCISTA": ("Demo Alcista S.A. (ficticia)", 0.0016, 0.013, 0.0),
    "DEMO-BAJISTA": ("Demo Bajista S.A. (ficticia)", -0.0008, 0.016, 0.0),
    "DEMO-LATERAL": ("Demo Lateral S.A. (ficticia)", 0.0, 0.010, 0.03),
    "DEMO-VOLATIL": ("Demo Volátil S.A. (ficticia)", 0.0004, 0.034, 0.0),
}

_END_DATE = date(2025, 12, 31)
_N_BARS = 520


def _business_days_ending(end: date, n: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


class DemoProvider(MarketDataProvider):
    name = "demo"
    is_simulated = True

    def supports(self, ticker: str) -> bool:
        return ticker in _PROFILES

    def list_tickers(self) -> list[str]:
        return list(_PROFILES)

    def get_asset_info(self, ticker: str) -> AssetInfo:
        self._check(ticker)
        return AssetInfo(
            ticker=ticker,
            name=_PROFILES[ticker][0],
            currency="USD",
            exchange="SIMULADO",
            asset_type="acción ficticia",
            description="Activo inventado para probar ARGOS. No cotiza en ningún mercado.",
        )

    def get_price_history(self, ticker, start=None, end=None) -> PriceHistory:
        self._check(ticker)
        _, drift, vol, reversion = _PROFILES[ticker]
        rng = random.Random(zlib.crc32(ticker.encode()))
        anchor = 100.0
        price = anchor
        bars: list[Bar] = []
        for d in _business_days_ending(_END_DATE, _N_BARS):
            pull = reversion * math.log(anchor / price)
            ret = drift + pull + rng.gauss(0, vol)
            open_ = price * (1 + rng.gauss(0, vol / 4))
            close = price * math.exp(ret)
            high = max(open_, close) * (1 + abs(rng.gauss(0, vol / 2)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, vol / 2)))
            volume = 1_000_000 * math.exp(rng.gauss(0, 0.3)) * (1 + 8 * abs(ret))
            bars.append(
                Bar(
                    date=d,
                    open=round(open_, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=round(volume),
                )
            )
            price = close
        if start:
            bars = [b for b in bars if b.date >= start]
        if end:
            bars = [b for b in bars if b.date <= end]
        return PriceHistory(
            ticker=ticker,
            bars=bars,
            provenance=Provenance(
                provider=self.name,
                source_description="Generador aleatorio determinista de ARGOS",
                is_simulated=True,
                retrieved_at=datetime.now(timezone.utc),
                warning=DEMO_WARNING,
            ),
        )

    def _check(self, ticker: str) -> None:
        if not self.supports(ticker):
            raise TickerNotFoundError(f"{ticker} no es un ticker de demostración.")
