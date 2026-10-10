"""Proveedor que lee históricos reales desde ficheros CSV locales.

Permite analizar datos reales sin conectar ninguna API. El formato exacto
está documentado en docs/CSV_FORMAT.md. Resumen:

    data/csv/<TICKER>.csv
    date,open,high,low,close,volume
    2024-01-02,187.15,188.44,183.89,185.64,82488700

- Fechas ISO `AAAA-MM-DD`, una fila por sesión (frecuencia DIARIA).
- Precios con punto decimal y sin separador de miles. Coma como separador de campos.
- Volumen obligatorio (usa 0 explícitamente si la fuente no lo tiene).
- Columnas extra (p. ej. `Adj Close`) se ignoran. Mayúsculas indiferentes.

El lector es estricto a propósito: ante cualquier duda RECHAZA el fichero con
un mensaje que indica la línea, en vez de corregir o rellenar datos en silencio.

Los ficheros cuyo nombre empieza por `DEMO-` se consideran SIEMPRE datos
simulados (sirven de ejemplo de formato) y así se marcan en toda la interfaz.
"""

from __future__ import annotations

import csv
import math
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

from argos.core.models import AssetInfo, Bar, PriceHistory, Provenance
from argos.data.base import DataProviderError, MarketDataProvider, TickerNotFoundError

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "csv"
_REQUIRED = ("date", "open", "high", "low", "close", "volume")
# AAAA-MM-DD, opcionalmente seguido de una hora 00:00(:00) (algunas exportaciones la añaden).
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:[ T]00:00(?::00)?)?$")
_MIN_DATE = date(1900, 1, 1)
#: Mediana de días naturales entre filas por encima de la cual el fichero no es diario.
_MAX_MEDIAN_GAP_DAYS = 4
DEMO_PREFIX = "DEMO-"


class CsvFormatError(DataProviderError):
    pass


def _parse_date(raw: str, line: int, fname: str) -> date:
    text = (raw or "").strip()
    m = _DATE_RE.match(text)
    if not m:
        if re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d", text):
            raise CsvFormatError(
                f"{fname}, línea {line}: '{text}' incluye hora. ARGOS solo acepta datos DIARIOS "
                "(una fila por sesión), no intradía."
            )
        raise CsvFormatError(
            f"{fname}, línea {line}: fecha '{text}' no válida. Formato obligatorio AAAA-MM-DD (p. ej. 2024-01-31)."
        )
    try:
        d = date.fromisoformat(m.group(1))
    except ValueError:
        raise CsvFormatError(f"{fname}, línea {line}: la fecha '{text}' no existe en el calendario.")
    if d < _MIN_DATE:
        raise CsvFormatError(f"{fname}, línea {line}: fecha {d} anterior a 1900; probablemente errónea.")
    if d > date.today():
        raise CsvFormatError(f"{fname}, línea {line}: fecha {d} en el futuro. Un histórico no puede contenerla.")
    return d


def _parse_number(raw: str, column: str, line: int, fname: str) -> float:
    text = (raw or "").strip()
    if text == "":
        hint = " Si la fuente no tiene volumen, escribe 0 explícitamente." if column == "volume" else ""
        raise CsvFormatError(f"{fname}, línea {line}: '{column}' está vacío.{hint}")
    try:
        value = float(text)
    except ValueError:
        hint = ""
        if "," in text:
            hint = " Usa punto como separador decimal y no uses separador de miles (1234.56)."
        raise CsvFormatError(f"{fname}, línea {line}: '{column}' = '{text}' no es un número.{hint}")
    if not math.isfinite(value):
        raise CsvFormatError(f"{fname}, línea {line}: '{column}' = '{text}' no es un número finito.")
    return value


class CsvProvider(MarketDataProvider):
    name = "csv"
    is_simulated = False  # por defecto; los ficheros DEMO-* se marcan como simulados

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.environ.get("ARGOS_CSV_DIR") or _DEFAULT_DIR)

    def _path(self, ticker: str) -> Path:
        return self.directory / f"{ticker}.csv"

    @staticmethod
    def is_demo_file(ticker: str) -> bool:
        return ticker.upper().startswith(DEMO_PREFIX)

    def supports(self, ticker: str) -> bool:
        return self._path(ticker).is_file()

    def list_tickers(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.stem.upper() for p in self.directory.glob("*.csv"))

    def describe(self) -> dict:
        return {"name": self.name, "is_simulated": False, "note": "Los ficheros DEMO-*.csv se tratan como simulados."}

    def get_asset_info(self, ticker: str) -> AssetInfo:
        if not self.supports(ticker):
            raise TickerNotFoundError(f"No existe {self._path(ticker).name}.")
        demo = self.is_demo_file(ticker)
        return AssetInfo(
            ticker=ticker,
            name=f"{ticker} (ejemplo simulado)" if demo else ticker,
            currency="desconocida",
            description=(
                "Fichero CSV de ejemplo con datos SIMULADOS." if demo
                else "Datos importados desde un fichero CSV local."
            ),
        )

    def get_price_history(self, ticker, start=None, end=None) -> PriceHistory:
        path = self._path(ticker)
        fname = path.name
        if not path.is_file():
            raise TickerNotFoundError(f"No existe {fname}.")
        bars: list[Bar] = []
        seen: dict[date, int] = {}
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            fields = [f.strip().lower() for f in header]
            if len(header) == 1 and ";" in header[0]:
                raise CsvFormatError(f"{fname}: el separador de campos debe ser la coma (,), no el punto y coma (;).")
            missing = [c for c in _REQUIRED if c not in fields]
            if missing:
                raise CsvFormatError(
                    f"{fname}: faltan columnas {missing}. Cabecera obligatoria: {','.join(_REQUIRED)}."
                )
            for line, row in enumerate(reader, start=2):
                row = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
                d = _parse_date(row["date"], line, fname)
                if d in seen:
                    raise CsvFormatError(
                        f"{fname}, línea {line}: la fecha {d} ya aparece en la línea {seen[d]}. "
                        "Debe haber una sola fila por sesión."
                    )
                seen[d] = line
                bar = Bar(
                    date=d,
                    **{c: _parse_number(row[c], c, line, fname) for c in ("open", "high", "low", "close", "volume")},
                )
                if (start and bar.date < start) or (end and bar.date > end):
                    continue
                bars.append(bar)

        if not seen:
            raise CsvFormatError(f"{fname}: el fichero no contiene ninguna fila de datos.")
        ordered = sorted(seen)
        if len(ordered) >= 3:
            gap = median((b - a).days for a, b in zip(ordered, ordered[1:]))
            if gap > _MAX_MEDIAN_GAP_DAYS:
                raise CsvFormatError(
                    f"{fname}: la separación típica entre filas es de {gap:g} días. Parece semanal o mensual; "
                    "ARGOS solo acepta datos DIARIOS."
                )

        demo = self.is_demo_file(ticker)
        return PriceHistory(
            ticker=ticker,
            bars=bars,
            provenance=Provenance(
                provider=self.name,
                source_description=f"Fichero local {fname}",
                is_simulated=demo,
                retrieved_at=datetime.now(timezone.utc),
                warning=(
                    "DATOS SIMULADOS: fichero CSV de ejemplo, no representa ningún mercado real."
                    if demo else
                    "Datos importados por el usuario: ARGOS no verifica su origen ni su exactitud."
                ),
            ),
        )
