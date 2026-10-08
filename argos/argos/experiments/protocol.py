"""Protocolos de experimento pre-registrados.

Un protocolo fija hipótesis, estrategia, costes, activos, periodos y criterios
de éxito ANTES de ver resultados. Su huella SHA-256 se guarda con cada
resultado registrado: si el fichero cambia después de haber registrado
resultados reales, ARGOS se niega a ejecutarlo (habría que crear otro experimento).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from argos.experiments.registry import ExperimentRegistry

PROTOCOLS_DIR = Path(__file__).resolve().parents[2] / "protocols"


class ProtocolAsset(BaseModel):
    ticker: str
    role: str
    description: str
    core: bool


class ProtocolPeriod(BaseModel):
    name: str
    start: date
    end: date
    note: str


class Protocol(BaseModel):
    id: str
    title: str
    registered_at: date
    hypothesis: dict[str, str]
    strategy: dict
    costs: dict
    assets: list[ProtocolAsset]
    data_requirements: dict
    periods: list[ProtocolPeriod]
    reserved_holdout: dict
    regime_classification: dict
    success_criteria: dict
    forbidden: list[str]
    status_note: str


class ProtocolChangedError(RuntimeError):
    pass


def load_protocol(experiment_id: str, directory: Path | None = None) -> tuple[Protocol, str, Path]:
    path = (directory or PROTOCOLS_DIR) / f"{experiment_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No existe el protocolo {path.name}.")
    raw = path.read_bytes()
    return Protocol.model_validate_json(raw), hashlib.sha256(raw).hexdigest(), path


def check_preregistered(experiment_id: str, sha: str, directory: Path | None = None) -> None:
    """Rechaza un protocolo cuya huella no coincide con la registrada en LOCKS.json.

    Protege también ANTES de la primera ejecución real (el registro de resultados aún está vacío).
    """
    locks_path = (directory or PROTOCOLS_DIR) / "LOCKS.json"
    if not locks_path.is_file():
        raise ProtocolChangedError(f"Falta {locks_path.name}: no se puede comprobar que {experiment_id} sea el pre-registrado.")
    lock = json.loads(locks_path.read_text(encoding="utf-8")).get(experiment_id)
    if not lock:
        raise ProtocolChangedError(f"{experiment_id} no figura en {locks_path.name}: no está pre-registrado.")
    if lock["sha256"] != sha:
        raise ProtocolChangedError(
            f"El protocolo {experiment_id} no coincide con el pre-registrado (commit {lock.get('preregistration_commit')}): "
            f"huella {sha[:12]}… ≠ {lock['sha256'][:12]}…. No se ejecuta. Si quieres cambiarlo, crea un experimento nuevo."
        )


def check_protocol_lock(protocol: Protocol, sha: str, registry: ExperimentRegistry) -> None:
    """Rechaza ejecutar un protocolo modificado después de haber registrado resultados reales."""
    previous = {r.protocol_sha256 for r in registry.list(experiment_id=protocol.id, include_dry_runs=False)}
    previous.discard(None)
    if previous and sha not in previous:
        raise ProtocolChangedError(
            f"El protocolo {protocol.id} ha cambiado después de registrar resultados reales. "
            "Eso permitiría ajustar el experimento a sus resultados. Crea un experimento nuevo "
            "(p. ej. EXP-002) en lugar de modificar este."
        )
