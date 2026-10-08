"""Comprueba la calidad de uno o varios CSV antes de usarlos.

Uso:
    python -m argos.data.check                 # todos los CSV de data/csv/
    python -m argos.data.check SPY KO          # solo esos
    python -m argos.data.check --protocolo EXP-001   # con los requisitos de un experimento

No modifica ningún fichero. Devuelve código 1 si algún fichero queda bloqueado.
"""

from __future__ import annotations

import argparse
import sys

from argos.data.base import DataProviderError
from argos.data.providers.csv_provider import CsvProvider
from argos.data.quality import QualityRequirements, assess_quality

ICON = {"ok": "OK   ", "aviso": "AVISO", "bloqueo": "BLOQ "}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Control de integridad de CSV para ARGOS.")
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--dir", default=None, help="Carpeta de CSV (por defecto data/csv).")
    ap.add_argument("--protocolo", default=None, help="Aplica los requisitos de datos de un experimento (p. ej. EXP-001).")
    args = ap.parse_args(argv)

    csv = CsvProvider(args.dir)
    requirements = None
    tickers = [t.upper() for t in args.tickers]
    if args.protocolo:
        from argos.experiments.protocol import load_protocol

        protocol, _, _ = load_protocol(args.protocolo)
        req = protocol.data_requirements
        requirements = QualityRequirements(
            required_start=req["required_start"], required_end=req["required_end"],
            max_start_tolerance_days=req.get("max_start_tolerance_days", 10), min_years=req.get("min_years"))
        tickers = tickers or [a.ticker for a in protocol.assets]
    tickers = tickers or csv.list_tickers()
    if not tickers:
        print(f"No hay ningún CSV en {csv.directory}. Consulta docs/DATOS_REALES.md.")
        return 1

    blocked = False
    for t in tickers:
        print(f"\n=== {t} ===")
        if not csv.supports(t):
            print(f"  FALTA  No existe {t}.csv en {csv.directory}")
            blocked = True
            continue
        try:
            history = csv.get_price_history(t)
        except DataProviderError as exc:
            print(f"  BLOQ   Formato: {exc}")
            blocked = True
            continue
        rep = assess_quality(history, requirements)
        src = csv.directory / f"{t}.source.txt"
        print(f"  {rep.summary()} · {rep.n_bars} sesiones · {rep.first_date} → {rep.last_date}"
              + (" · SIMULADO" if history.provenance.is_simulated else ""))
        print(f"  Procedencia: {src.read_text(encoding='utf-8').strip() if src.is_file() else 'NO DOCUMENTADA (crea ' + src.name + ')'}")
        for c in rep.checks:
            print(f"  {ICON[c.status]}  {c.label}: {c.detail}")
            for e in c.examples:
                print(f"           · {e}")
        blocked |= rep.blocked
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
