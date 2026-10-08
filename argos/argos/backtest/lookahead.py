"""Auditoría anti look-ahead (uso de información futura).

Método: si una estrategia solo usa datos disponibles hasta cada fecha, entonces
las señales que produce con el histórico COMPLETO hasta la fecha t deben ser
idénticas a las que produce cuando le damos el histórico CORTADO en t.
Si al cortar los datos cambia alguna señal anterior al corte, la estrategia
estaba mirando el futuro.

Se ejecuta automáticamente en cada backtest; si falla, el backtest se rechaza.
"""

from __future__ import annotations

import pandas as pd

from argos.backtest.models import LookAheadAudit
from argos.strategy.base import Strategy

DEFAULT_CUTOFFS = 8


class LookAheadError(ValueError):
    pass


def _key(signals) -> list[tuple]:
    return [(s.date, s.action) for s in signals]


def audit_lookahead(strategy: Strategy, df: pd.DataFrame, n_cutoffs: int = DEFAULT_CUTOFFS) -> LookAheadAudit:
    full = strategy.generate_signals(df)
    n = len(df)
    first = min(max(strategy.min_bars, 1), n - 1)
    candidates = sorted({int(first + (n - 1 - first) * k / max(1, n_cutoffs - 1)) for k in range(n_cutoffs)})
    # Cortar también justo en las fechas de señal (y el día anterior): es donde un sesgo se notaría.
    pos = {ts.date(): i for i, ts in enumerate(df.index)}
    for s in full[:20]:
        i = pos[s.date]
        candidates += [i, max(0, i - 1)]
    cutoffs = sorted(set(c for c in candidates if 0 <= c < n))
    failures = []
    for c in cutoffs:
        cut_date = df.index[c].date()
        expected = [k for k in _key(full) if k[0] <= cut_date]
        got = _key(strategy.generate_signals(df.iloc[: c + 1]))
        if got != expected:
            failures.append(
                f"Con datos hasta {cut_date} la estrategia da {len(got)} señal(es); "
                f"con el histórico completo da {len(expected)} hasta esa fecha."
            )
    return LookAheadAudit(
        passed=not failures,
        checked_cutoffs=len(cutoffs),
        method=(
            "Se recalculan las señales cortando los datos en varias fechas y se comprueba que las señales "
            "hasta cada corte son idénticas a las calculadas con el histórico completo."
        ),
        failures=failures,
    )
