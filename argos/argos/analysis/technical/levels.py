"""Soportes y resistencias (versión simplificada).

Método: máximos y mínimos locales ("pivots") — una barra cuyo máximo (o mínimo)
es el extremo de las `k` barras a cada lado. Se agrupan los que están muy
cerca y se devuelven los más próximos al precio actual. Es una aproximación
didáctica, no un método definitivo.
"""

from __future__ import annotations

import pandas as pd


def _pivots(values: pd.Series, k: int, highs: bool) -> list[float]:
    out = []
    arr = values.to_numpy()
    for i in range(k, len(arr) - k):
        window = arr[i - k : i + k + 1]
        if (highs and arr[i] == window.max()) or (not highs and arr[i] == window.min()):
            out.append(float(arr[i]))
    return out


def _cluster(levels: list[float], tolerance: float) -> list[float]:
    clusters: list[list[float]] = []
    for lvl in sorted(levels):
        if clusters and abs(lvl / clusters[-1][-1] - 1) <= tolerance:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])
    return [sum(c) / len(c) for c in clusters]


def support_resistance(
    df: pd.DataFrame, lookback: int = 120, k: int = 5, tolerance: float = 0.015
) -> dict[str, float | None]:
    recent = df.tail(lookback)
    price = float(recent["close"].iloc[-1])
    levels = _cluster(
        _pivots(recent["high"], k, highs=True) + _pivots(recent["low"], k, highs=False),
        tolerance,
    )
    below = [lvl for lvl in levels if lvl < price]
    above = [lvl for lvl in levels if lvl > price]
    return {
        "support": max(below) if below else None,
        "resistance": min(above) if above else None,
    }
