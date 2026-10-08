"""Ajusta por dividendos (y splits) un CSV que trae una columna `Adj Close`.

Uso:
    python -m argos.tools.adjust_csv descargado.csv data/csv/KO.csv

Para cada fila: factor = Adj Close / Close, y se multiplican open, high, low y
close por ese factor (el volumen no se toca). Así las cuatro columnas quedan en
la misma escala ajustada, que es lo que necesita el backtest: ejecuta a la
apertura y valora al cierre.

No inventa ni rellena nada: si una fila no tiene todos los valores, se detiene
e indica la línea. Añade al fichero `.source.txt` una nota con el ajuste aplicado.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REQUIRED = ("date", "open", "high", "low", "close", "adj close", "volume")


def adjust(src: Path, dst: Path) -> int:
    with src.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = {f.strip().lower(): f for f in (reader.fieldnames or [])}
        missing = [c for c in REQUIRED if c not in fields]
        if missing:
            raise SystemExit(f"{src.name}: faltan columnas {missing}.")
        rows = []
        for line, row in enumerate(reader, start=2):
            try:
                close = float(row[fields["close"]])
                factor = float(row[fields["adj close"]]) / close
                vals = [float(row[fields[c]]) * factor for c in ("open", "high", "low")]
                volume = row[fields["volume"]].strip()
                float(volume)
            except (ValueError, ZeroDivisionError, TypeError) as exc:
                raise SystemExit(f"{src.name}, línea {line}: valor no válido ({exc}). No se rellena nada: corrige el fichero.")
            rows.append([row[fields["date"]].strip(), *(f"{v:.6f}" for v in vals), f"{close * factor:.6f}", volume])
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        w.writerows(rows)
    note = dst.with_suffix(".source.txt")
    with note.open("a", encoding="utf-8") as fh:
        fh.write(f"\nAjustado con argos.tools.adjust_csv desde {src.name}: OHLC × (Adj Close / Close).\n")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("entrada", type=Path)
    ap.add_argument("salida", type=Path)
    args = ap.parse_args(argv)
    n = adjust(args.entrada, args.salida)
    print(f"{n} filas ajustadas → {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
