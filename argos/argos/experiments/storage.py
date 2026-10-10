"""Dónde guarda sus datos cada experimento, para que nunca se mezclen.

    EXP-001  → data/csv/            (ubicación histórica; no se mueve)
    EXP-00N  → data/csv/EXP-00N/    (cualquier experimento posterior)
    Resultados y registro de EXP-00N (N ≥ 2) → data/experiments/EXP-00N/

Los originales de Tiingo comparten data/raw/tiingo/: cada descarga es un fichero nuevo con marca de tiempo
y el manifiesto solo crece. Cada experimento convierte la descarga cuyo rango coincide EXACTAMENTE con el de
su protocolo, así que la de otro experimento nunca se usa por accidente.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos.experiments.registry import ARGOS_ROOT

LEGACY = "EXP-001"


class StorageError(ValueError):
    pass


def csv_dir_for(experiment_id: str, base: Path | None = None) -> Path:
    from argos.data.sources import tiingo

    root = Path(base) if base is not None else tiingo.CSV_DIR
    return root if experiment_id == LEGACY else root / experiment_id


def results_dir_for(experiment_id: str, base: Path | None = None) -> Path:
    if experiment_id == LEGACY:
        raise StorageError("EXP-001 conserva su ubicación y su registro originales; no se usa esta función.")
    return (Path(base) if base is not None else ARGOS_ROOT / "data" / "experiments") / experiment_id


def check_csv_dir(experiment_id: str, directory: Path) -> None:
    """Impide que un experimento posterior escriba en la carpeta de EXP-001."""
    from argos.data.sources import tiingo

    if experiment_id != LEGACY and Path(directory).resolve() == Path(tiingo.CSV_DIR).resolve():
        raise StorageError(
            f"{experiment_id} no puede usar {directory}: es la carpeta de datos de EXP-001. Usa {csv_dir_for(experiment_id)}.")


def download_for_range(ticker: str, start: date, end: date, raw_dir: Path) -> dict:
    """Última descarga correcta de `ticker` con exactamente el rango [start, end] del protocolo."""
    from argos.data.sources import tiingo

    entries = [e for e in tiingo.read_manifest(raw_dir) if e["ticker"] == ticker and e.get("status") == "ok"
               and e["start"] == start.isoformat() and e["end"] == end.isoformat()]
    if not entries:
        raise tiingo.RawDataError(
            f"{ticker}: no hay ninguna descarga con el rango del protocolo ({start} → {end}) en {raw_dir}. "
            "Descarga primero con ese mismo --protocolo.")
    return entries[-1]
