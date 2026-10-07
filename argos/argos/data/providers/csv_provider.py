"""Proveedor que lee históricos reales desde ficheros CSV locales.

Permite analizar datos reales sin conectar ninguna API: descarga el histórico
diario de un activo (por ejemplo, la exportación de tu bróker o de una web de
datos) y guárdalo como `data/csv/<TICKER>.csv` con las columnas:

    date,open,high,low,close,volume

ARGOS no verifica el origen del fichero; la procedencia se muestra tal cual.
"""

from __future__ import annotations

import csv
import os
from datetime import date, datetime, timezone
from pathlib import Path

from argos.core.models import AssetInfo, Bar, PriceHistory, Provenance
from argos.data.base import DataProviderError, MarketDataProvider, TickerNotFoundError

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "csv"
_REQUIRED = ("date", "open", "high", "low", "close", "volume")


class CsvProvider(MarketDataProvider):
    name = "csv"
    is_simulated = False

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.environ.get("ARGOS_CSV_DIR") or _DEFAULT_DIR)

    def _path(self, ticker: str) -> Path:
        return self.directory / f"{ticker}.csv"

    def supports(self, ticker: str) -> bool:
        return self._path(ticker).is_file()

    def list_tickers(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.stem.upper() for p in self.directory.glob("*.csv"))

    def get_asset_info(self, ticker: str) -> AssetInfo:
        if not self.supports(ticker):
            raise TickerNotFoundError(f"No existe {self._path(ticker).name}.")
        return AssetInfo(
            ticker=ticker,
            name=ticker,
            currency="desconocida",
            description="Datos importados desde un fichero CSV local.",
        )

    def get_price_history(self, ticker, start=None, end=None) -> PriceHistory:
        path = self._path(ticker)
        if not path.is_file():
            raise TickerNotFoundError(f"No existe {path.name}.")
        bars: list[Bar] = []
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            fields = [f.strip().lower() for f in (reader.fieldnames or [])]
            missing = [c for c in _REQUIRED if c not in fields]
            if missing:
                raise DataProviderError(f"{path.name}: faltan columnas {missing}.")
            for row in reader:
                row = {k.strip().lower(): v for k, v in row.items()}
                try:
                    bar = Bar(
                        date=date.fromisoformat(row["date"].strip()[:10]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"] or 0),
                    )
                except (ValueError, TypeError) as exc:
                    raise DataProviderError(f"{path.name}: fila no válida {row}: {exc}")
                if (start and bar.date < start) or (end and bar.date > end):
                    continue
                bars.append(bar)
        return PriceHistory(
            ticker=ticker,
            bars=bars,
            provenance=Provenance(
                provider=self.name,
                source_description=f"Fichero local {path.name}",
                is_simulated=False,
                retrieved_at=datetime.now(timezone.utc),
                warning="Datos importados por el usuario: ARGOS no verifica su origen ni su exactitud.",
            ),
        )
