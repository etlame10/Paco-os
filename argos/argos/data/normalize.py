"""Normalización y validación de datos, común a todos los proveedores.

Ningún dato se corrige ni se inventa: las barras inválidas se descartan y cada
descarte queda anotado en `normalization_notes` para que sea visible.
"""

from __future__ import annotations

import re

from argos.core.models import Bar, PriceHistory

_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,19}$")


def normalize_ticker(raw: str) -> str:
    ticker = (raw or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"Ticker no válido: {raw!r}")
    return ticker


def _bar_problem(bar: Bar) -> str | None:
    prices = (bar.open, bar.high, bar.low, bar.close)
    if any(p != p or p <= 0 for p in prices):  # p != p detecta NaN
        return "precio no positivo o vacío"
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        return "máximo/mínimo incoherente con apertura/cierre"
    if bar.volume != bar.volume or bar.volume < 0:
        return "volumen negativo o vacío"
    return None


def normalize_history(history: PriceHistory) -> PriceHistory:
    """Ordena por fecha, elimina duplicados y descarta barras inválidas."""
    notes = list(history.normalization_notes)
    by_date: dict = {}
    duplicates = 0
    for bar in history.bars:
        if bar.date in by_date:
            duplicates += 1
        by_date[bar.date] = bar  # la última aparición prevalece
    if duplicates:
        notes.append(f"{duplicates} barra(s) con fecha duplicada; se conserva la última.")

    clean: list[Bar] = []
    for d in sorted(by_date):
        bar = by_date[d]
        problem = _bar_problem(bar)
        if problem:
            notes.append(f"Barra del {d.isoformat()} descartada: {problem}.")
        else:
            clean.append(bar)

    return history.model_copy(update={"bars": clean, "normalization_notes": notes})
