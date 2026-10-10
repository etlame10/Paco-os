"""Ensayo del procedimiento con DATOS SIMULADOS.

Genera, para cada activo del protocolo, un CSV `DEMO-<TICKER>.csv` con una
serie inventada que alterna fases alcistas, bajistas y laterales. El prefijo
DEMO- hace que ARGOS lo marque como simulado en todas partes, y los registros
quedan como `dry_run`: nunca cuentan como resultado del experimento.

Sirve SOLO para comprobar que el procedimiento funciona de principio a fin.
"""

from __future__ import annotations

import math
import random
import zlib
from datetime import date, timedelta
from pathlib import Path

from argos.experiments.protocol import Protocol

# (deriva diaria, volatilidad diaria) por fase
_PHASES = {"alcista": (0.0008, 0.010), "bajista": (-0.0012, 0.022), "lateral": (0.0, 0.009)}


def _business_days(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def write_demo_dataset(protocol: Protocol, directory: Path) -> dict[str, str]:
    req = protocol.data_requirements
    days = _business_days(date.fromisoformat(req["required_start"]), date.fromisoformat(req["required_end"]))
    mapping = {}
    for asset in protocol.assets:
        name = f"DEMO-{asset.ticker}"
        rng = random.Random(zlib.crc32(name.encode()))
        price, phase, left = 100.0, "alcista", 0
        lines = ["date,open,high,low,close,volume"]
        for d in days:
            if left == 0:
                phase = rng.choices(list(_PHASES), weights=[0.5, 0.2, 0.3])[0]
                left = rng.randint(120, 500)
            left -= 1
            drift, vol = _PHASES[phase]
            open_ = price * (1 + rng.gauss(0, vol / 4))
            close = price * math.exp(drift + rng.gauss(0, vol))
            high = max(open_, close) * (1 + abs(rng.gauss(0, vol / 2)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, vol / 2)))
            lines.append(f"{d},{open_:.4f},{high:.4f},{low:.4f},{close:.4f},{int(1e6 * math.exp(rng.gauss(0, 0.3)))}")
            price = close
        (directory / f"{name}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (directory / f"{name}.source.txt").write_text(
            "SIMULADO: serie generada por argos.experiments.dryrun para ensayar el procedimiento. No es un dato real.",
            encoding="utf-8")
        mapping[asset.ticker] = name
    return mapping
