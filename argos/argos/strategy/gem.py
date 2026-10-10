"""GEM (dual momentum de Antonacci) tal y como lo fija protocols/EXP-002.json.

Día de decisión d(m): última sesión NYSE del mes natural m (según argos/data/calendar_us.py, no según los
datos: así truncar los datos no puede convertir un día cualquiera en fin de mes).

    R_X(m) = Pc_X(d(m)) / Pc_X(d(m − L)) − 1          (Pc = cierre ajustado; L = lookback en meses)

Regla principal (S&P 500 primero):           Variante S1 (filtro sobre el ganador):
    R_SPY ≤ R_BIL            → AGG               max(R_SPY, R_VEU) ≤ R_BIL → AGG
    si no, R_SPY ≥ R_VEU     → SPY               si no, R_SPY ≥ R_VEU      → SPY
    si no                    → VEU               si no                     → VEU

Se comparan valores sin redondear. Solo se usan cierres hasta d(m) incluido.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Literal

from argos.backtest.portfolio import Market
from argos.data.calendar_us import sessions as nyse_sessions

Variant = Literal["principal", "S1"]
US, EXUS, BONDS, BILLS = "SPY", "VEU", "AGG", "BIL"
GEM_TICKERS = (US, EXUS, BONDS, BILLS)


@dataclass(frozen=True)
class Decision:
    date: date
    index: int  # sesión del mercado
    reference_date: date  # d(m − L)
    r_spy: float
    r_veu: float
    r_bil: float
    target: str


@lru_cache(maxsize=None)
def nyse_month_end(year: int, month: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    days = nyse_sessions(date(year, month, 1), date.fromordinal(nxt.toordinal() - 1))
    if not days:
        raise ValueError(f"El calendario NYSE no tiene sesiones en {year}-{month:02d}.")
    return days[-1]


def shift_month(year: int, month: int, k: int) -> tuple[int, int]:
    n = year * 12 + (month - 1) - k
    return n // 12, n % 12 + 1


def gem_target(r_spy: float, r_veu: float, r_bil: float, variant: Variant = "principal") -> str:
    if variant == "principal":
        if r_spy <= r_bil:
            return BONDS
    elif variant == "S1":
        if max(r_spy, r_veu) <= r_bil:
            return BONDS
    else:
        raise ValueError(f"Variante desconocida: {variant}")
    return US if r_spy >= r_veu else EXUS


def gem_decisions(market: Market, lookback_months: int = 12, variant: Variant = "principal") -> list[Decision]:
    """Todas las decisiones posibles con los datos del mercado (una por fin de mes con historia suficiente)."""
    if lookback_months < 1:
        raise ValueError("lookback_months debe ser ≥ 1.")
    missing = set(GEM_TICKERS) - set(market.closes)
    if missing:
        raise ValueError(f"Faltan activos para GEM: {sorted(missing)}.")
    pos = {d: i for i, d in enumerate(market.sessions)}
    out: list[Decision] = []
    months = sorted({(d.year, d.month) for d in market.sessions})
    for y, m in months:
        d = nyse_month_end(y, m)
        if d not in pos:  # el mes aún no ha terminado en estos datos, o falta la sesión
            continue
        ref = nyse_month_end(*shift_month(y, m, lookback_months))
        if ref not in pos:
            continue
        i, j = pos[d], pos[ref]
        r = {t: float(market.closes[t][i] / market.closes[t][j] - 1) for t in (US, EXUS, BILLS)}
        out.append(Decision(d, i, ref, r[US], r[EXUS], r[BILLS], gem_target(r[US], r[EXUS], r[BILLS], variant)))
    return out
