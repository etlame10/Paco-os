"""Generador de originales SINTÉTICOS con el formato de Tiingo, solo para tests.

No representa ningún activo real. Produce precios sin ajustar con eventos conocidos
(split y dividendos) y sus precios ajustados hacia atrás con el método multiplicativo:

    factor_t = Π_{eventos e con fecha ex > t} m_e,   m_e = (1 − D_e / close_{e−1}) / split_e
    adj_t    = precio_t × factor_t
    adjVolume_t = volume_t × Π_{splits posteriores} split_e
"""

from __future__ import annotations

import math
import random
from datetime import date

from argos.data.calendar_us import sessions

HEADER = "date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume,divCash,splitFactor"


def build(
    start: date = date(2007, 1, 3),
    end: date = date(2025, 12, 31),
    split_on: date | None = date(2014, 6, 9),
    split: float = 2.0,
    dividend: float = 0.30,
    seed: int = 7,
):
    """Devuelve (filas, texto CSV). Cada fila es un dict con valores numéricos."""
    days = sessions(start, end)
    rng = random.Random(seed)
    div_days = set()
    for y in range(start.year, end.year + 1):  # primera sesión desde el día 10 de mar/jun/sep/dic
        for m in (3, 6, 9, 12):
            cand = [d for d in days if d.year == y and d.month == m and d.day >= 10]
            if cand:
                div_days.add(cand[0])
    rows, p = [], 60.0
    for d in days:
        if split_on and d == split_on:
            p /= split
        p *= math.exp(rng.gauss(0.0003, 0.012))
        c = round(p, 2)
        o = round(p * (1 + rng.gauss(0, 0.003)), 2)
        h = round(max(o, c) * (1 + abs(rng.gauss(0, 0.004))) + 0.01, 2)
        lo = round(min(o, c) * (1 - abs(rng.gauss(0, 0.004))) - 0.01, 2)
        rows.append({"date": d, "open": o, "high": h, "low": lo, "close": c, "volume": 1_000_000 + rng.randint(0, 9999),
                     "divCash": dividend if d in div_days else 0.0,
                     "splitFactor": split if (split_on and d == split_on) else 1.0})
    # Ajuste hacia atrás.
    factor, vol_factor = 1.0, 1.0
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        r["f"], r["vf"] = factor, vol_factor
        if i > 0 and (r["divCash"] > 0 or r["splitFactor"] != 1):
            factor *= (1 - r["divCash"] / rows[i - 1]["close"]) / r["splitFactor"]
            vol_factor *= r["splitFactor"]
    return rows, render(rows)


def render(rows) -> str:
    out = [HEADER]
    for r in rows:
        f, vf = r["f"], r["vf"]
        out.append(",".join([
            r["date"].isoformat(), f"{r['close']}", f"{r['high']}", f"{r['low']}", f"{r['open']}", f"{r['volume']}",
            f"{r['close'] * f:.6f}", f"{r['high'] * f:.6f}", f"{r['low'] * f:.6f}", f"{r['open'] * f:.6f}",
            f"{r['volume'] * vf:.1f}", f"{r['divCash']}", f"{r['splitFactor']}",
        ]))
    return "\n".join(out) + "\n"
