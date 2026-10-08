"""Registro local de experimentos (append-only, un JSON por línea).

Cada backtest registrado guarda lo necesario para reproducirlo y compararlo:
fecha, versión de ARGOS, commit de git, activo, origen y huella (SHA-256) del
fichero de datos, periodo, estrategia, parámetros, costes y métricas.

Nunca se reescriben líneas: si algo cambia, se registra un experimento nuevo.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from argos import __version__
from argos.backtest.models import BacktestReport

ARGOS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ARGOS_ROOT / "data" / "experiments" / "registry.jsonl"


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ARGOS_ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExperimentRecord(BaseModel):
    record_id: str
    recorded_at: str
    argos_version: str
    git_commit: str | None
    experiment_id: str | None  # p. ej. "EXP-001"; None para backtests sueltos
    protocol_sha256: str | None
    period_name: str | None  # "desarrollo", "fuera_de_muestra"...
    dry_run: bool  # ensayo con datos simulados: nunca cuenta como resultado
    ticker: str
    is_simulated_data: bool
    data_source: str
    data_sha256: str | None
    data_quality: str
    period_start: str
    period_end: str
    strategy: str
    params: dict
    initial_capital: float
    commission_pct: float
    slippage_pct: float
    strategy_metrics: dict
    benchmark_metrics: dict
    return_difference: float
    lookahead_audit_passed: bool
    verdict: str


class ExperimentRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("ARGOS_REGISTRY") or DEFAULT_PATH)

    def record(
        self,
        report: BacktestReport,
        *,
        experiment_id: str | None = None,
        protocol_sha256: str | None = None,
        period_name: str | None = None,
        dry_run: bool = False,
        data_file: Path | None = None,
    ) -> ExperimentRecord:
        tr = report.transparency
        rec = ExperimentRecord(
            record_id=uuid.uuid4().hex[:12],
            recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            argos_version=__version__,
            git_commit=git_commit(),
            experiment_id=experiment_id,
            protocol_sha256=protocol_sha256,
            period_name=period_name,
            dry_run=dry_run or report.is_simulated_data,
            ticker=report.ticker,
            is_simulated_data=report.is_simulated_data,
            data_source=f"{tr.data['provider']}: {tr.data['source']}",
            data_sha256=file_sha256(data_file) if data_file else None,
            data_quality=report.data_quality.summary(),
            period_start=tr.period["start"],
            period_end=tr.period["end"],
            strategy=tr.strategy["name"],
            params=tr.strategy["params"],
            initial_capital=report.strategy.metrics.initial_capital,
            commission_pct=report.strategy.simulation.config.commission_pct,
            slippage_pct=report.strategy.simulation.config.slippage_pct,
            strategy_metrics=report.strategy.metrics.model_dump(),
            benchmark_metrics=report.benchmark.metrics.model_dump(),
            return_difference=report.strategy.metrics.total_return - report.benchmark.metrics.total_return,
            lookahead_audit_passed=report.lookahead_audit.passed,
            verdict=report.comparison.verdict,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(rec.model_dump_json() + "\n")
        return rec

    def list(self, *, experiment_id: str | None = None, include_dry_runs: bool = True) -> list[ExperimentRecord]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = ExperimentRecord.model_validate_json(line)
            if experiment_id and rec.experiment_id != experiment_id:
                continue
            if not include_dry_runs and rec.dry_run:
                continue
            out.append(rec)
        return out
