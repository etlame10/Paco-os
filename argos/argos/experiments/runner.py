"""Ejecutor de experimentos pre-registrados.

HIPÓTESIS → DATOS → EXPERIMENTO → RESULTADOS → VALIDACIÓN → CONCLUSIÓN

Uso:
    python -m argos.experiments.runner EXP-001               # datos reales de data/csv/
    python -m argos.experiments.runner EXP-001 --ensayo-demo # ensayo con datos SIMULADOS

El ejecutor no decide nada sobre la estrategia: aplica el protocolo tal cual,
registra cada backtest y evalúa los criterios fijados de antemano.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from argos import __version__
from argos.backtest.models import BacktestConfig
from argos.backtest.service import BacktestService
from argos.data.base import DataProviderError, TickerNotFoundError
from argos.data.providers.csv_provider import CsvProvider
from argos.data.quality import DataQualityReport, QualityRequirements
from argos.data.registry import ProviderRegistry
from argos.experiments.protocol import Protocol, check_preregistered, check_protocol_lock, load_protocol
from argos.experiments.registry import ARGOS_ROOT, ExperimentRegistry, file_sha256, git_commit
from argos.experiments.regimes import RegimeSummary, YearResult, summarize_regimes, yearly_results
from argos.strategy.base import get_strategy

RESULTS_DIR = ARGOS_ROOT / "data" / "experiments" / "results"


class PeriodRow(BaseModel):
    ticker: str
    role: str
    core: bool
    period_name: str
    start: str
    end: str
    strategy_return: float
    benchmark_return: float
    difference: float
    strategy_cagr: float | None
    benchmark_cagr: float | None
    strategy_final: float
    benchmark_final: float
    strategy_max_dd: float
    benchmark_max_dd: float
    strategy_vol: float | None
    benchmark_vol: float | None
    strategy_sharpe: float | None
    benchmark_sharpe: float | None
    n_trades: int
    win_rate: float | None
    best_trade: float | None
    worst_trade: float | None
    exposure: float
    record_id: str


class AssetStatus(BaseModel):
    ticker: str
    role: str
    core: bool
    status: str  # "evaluado" | "sin datos" | "bloqueado por calidad" | "error"
    detail: str
    source_note: str | None = None
    data_file: str | None = None
    data_sha256: str | None = None
    quality: DataQualityReport | None = None


class CriterionResult(BaseModel):
    name: str
    text: str
    count: int | None
    total: int | None
    needed: int
    met: bool | None  # None: no evaluable


class ExperimentResult(BaseModel):
    experiment_id: str
    title: str
    protocol_sha256: str
    run_at: str
    argos_version: str
    git_commit: str | None
    dry_run: bool
    protocol: Protocol
    assets: list[AssetStatus]
    rows: list[PeriodRow]
    years: list[YearResult]
    regimes: dict[str, list[RegimeSummary]]
    criteria: list[CriterionResult]


def sharpe_better(r: PeriodRow) -> bool | None:
    """Criterio principal: Sharpe de la estrategia > Sharpe de Buy & Hold (None si falta alguno)."""
    if r.strategy_sharpe is None or r.benchmark_sharpe is None:
        return None
    return r.strategy_sharpe > r.benchmark_sharpe


def drawdown_better(r: PeriodRow) -> bool:
    """Criterio secundario: caída máxima MENOR (las caídas son negativas: −10% > −30%)."""
    return r.strategy_max_dd > r.benchmark_max_dd


def _criterion(rows: list[PeriodRow], name: str, text: str, pred, needed: int, min_assets: int) -> CriterionResult:
    core = [r for r in rows if r.core and r.period_name == "fuera_de_muestra"]
    evaluable = [r for r in core if pred(r) is not None]
    if len(evaluable) < min_assets:
        return CriterionResult(name=name, text=text, count=None, total=len(evaluable), needed=needed, met=None)
    count = sum(bool(pred(r)) for r in evaluable)
    return CriterionResult(name=name, text=text, count=count, total=len(evaluable), needed=needed, met=count >= needed)


def run_experiment(
    experiment_id: str,
    *,
    data_dir: Path | None = None,
    registry: ExperimentRegistry | None = None,
    dry_run: bool = False,
    protocol_dir: Path | None = None,
    ticker_map: dict[str, str] | None = None,
) -> ExperimentResult:
    protocol, sha, _ = load_protocol(experiment_id, protocol_dir)
    registry = registry or ExperimentRegistry()
    if not dry_run:
        check_preregistered(experiment_id, sha, protocol_dir)
        check_protocol_lock(protocol, sha, registry)

    csv = CsvProvider(data_dir)
    service = BacktestService(registry=ProviderRegistry([csv]))
    req = protocol.data_requirements
    requirements = QualityRequirements(
        required_start=req["required_start"], required_end=req["required_end"],
        max_start_tolerance_days=req.get("max_start_tolerance_days", 10), min_years=req.get("min_years"),
    )
    costs = protocol.costs
    bull = protocol.regime_classification["bull_threshold"]
    bear = protocol.regime_classification["bear_threshold"]

    assets: list[AssetStatus] = []
    rows: list[PeriodRow] = []
    years: list[YearResult] = []
    for asset in protocol.assets:
        file_ticker = (ticker_map or {}).get(asset.ticker, asset.ticker)
        path = csv.directory / f"{file_ticker}.csv"
        source_file = csv.directory / f"{file_ticker}.source.txt"
        source_note = source_file.read_text(encoding="utf-8").strip() if source_file.is_file() else None
        base = dict(ticker=asset.ticker, role=asset.role, core=asset.core, source_note=source_note)
        try:
            loaded = service.load(file_ticker, requirements)
        except TickerNotFoundError:
            assets.append(AssetStatus(**base, status="sin datos", detail=f"No existe {path.name} en {csv.directory}."))
            continue
        except DataProviderError as exc:
            assets.append(AssetStatus(**base, status="error", detail=str(exc)))
            continue
        _, history, quality = loaded
        meta = dict(data_file=str(path.relative_to(ARGOS_ROOT)) if path.is_relative_to(ARGOS_ROOT) else str(path),
                    data_sha256=file_sha256(path), quality=quality)
        if not dry_run and history.provenance.is_simulated:
            assets.append(AssetStatus(**base, **meta, status="error",
                                      detail="El fichero está marcado como SIMULADO: no puede usarse en un experimento real."))
            continue
        if quality.blocked:
            failed = "; ".join(f"{c.label}: {c.detail}" for c in quality.checks if c.status == "bloqueo")
            assets.append(AssetStatus(**base, **meta, status="bloqueado por calidad", detail=failed))
            continue
        assets.append(AssetStatus(**base, **meta, status="evaluado", detail=quality.summary()))

        for period in protocol.periods:
            config = BacktestConfig(
                initial_capital=costs["initial_capital"], commission_pct=costs["commission_pct"],
                slippage_pct=costs["slippage_pct"], start=period.start, end=period.end,
            )
            strategy = get_strategy(protocol.strategy["name"], **protocol.strategy["params"])
            report = service.run_strategy(file_ticker, strategy, config, preloaded=loaded)
            rec = registry.record(report, experiment_id=protocol.id, protocol_sha256=sha,
                                  period_name=period.name, dry_run=dry_run, data_file=path)
            s, b = report.strategy.metrics, report.benchmark.metrics
            rows.append(PeriodRow(
                ticker=asset.ticker, role=asset.role, core=asset.core, period_name=period.name,
                start=report.transparency.period["start"], end=report.transparency.period["end"],
                strategy_return=s.total_return, benchmark_return=b.total_return,
                difference=s.total_return - b.total_return,
                strategy_cagr=s.annualized_return, benchmark_cagr=b.annualized_return,
                strategy_final=s.final_capital, benchmark_final=b.final_capital,
                strategy_max_dd=s.max_drawdown, benchmark_max_dd=b.max_drawdown,
                strategy_vol=s.volatility, benchmark_vol=b.volatility,
                strategy_sharpe=s.sharpe, benchmark_sharpe=b.sharpe,
                n_trades=s.n_trades, win_rate=s.win_rate, best_trade=s.best_trade_return,
                worst_trade=s.worst_trade_return, exposure=s.exposure, record_id=rec.record_id,
            ))
            years += yearly_results(report, period.name, bull, bear)

    crit = protocol.success_criteria
    min_assets = crit["min_core_assets_with_valid_data"]
    criteria = [
        _criterion(rows, "principal", crit["primary"], sharpe_better, 3, min_assets),
        _criterion(rows, "secundario", crit["secondary"], drawdown_better, 3, min_assets),
    ]
    regimes = {p.name: summarize_regimes([y for y in years if y.period_name == p.name]) for p in protocol.periods}
    regimes["total"] = summarize_regimes(years)
    return ExperimentResult(
        experiment_id=protocol.id, title=protocol.title, protocol_sha256=sha,
        run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), argos_version=__version__,
        git_commit=git_commit(), dry_run=dry_run, protocol=protocol, assets=assets, rows=rows,
        years=years, regimes=regimes, criteria=criteria,
    )


def save_result(result: ExperimentResult, out_root: Path | None = None) -> Path:
    from argos.experiments.report import render_markdown

    stamp = result.run_at.replace(":", "").replace("-", "")[:15]
    folder = (out_root or RESULTS_DIR) / result.experiment_id / (f"ENSAYO-{stamp}" if result.dry_run else stamp)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    (folder / "report.md").write_text(render_markdown(result), encoding="utf-8")
    return folder


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ejecuta un experimento pre-registrado de ARGOS.")
    ap.add_argument("experiment_id")
    ap.add_argument("--data-dir", type=Path, default=None, help="Carpeta de CSV (por defecto data/csv).")
    ap.add_argument("--ensayo-demo", action="store_true",
                    help="Ensayo del procedimiento con datos SIMULADOS generados al vuelo. No es el experimento.")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.ensayo_demo:
        from argos.experiments.dryrun import write_demo_dataset

        protocol, _, _ = load_protocol(args.experiment_id)
        tmp = Path(tempfile.mkdtemp(prefix="argos-ensayo-"))
        mapping = write_demo_dataset(protocol, tmp)
        result = run_experiment(args.experiment_id, data_dir=tmp, dry_run=True, ticker_map=mapping)
    else:
        result = run_experiment(args.experiment_id, data_dir=args.data_dir)
    folder = save_result(result, args.out)
    evaluated = sum(a.status == "evaluado" for a in result.assets)
    print(f"{'ENSAYO (datos simulados)' if result.dry_run else 'Experimento'} {result.experiment_id}: "
          f"{evaluated}/{len(result.assets)} activos evaluados.")
    for a in result.assets:
        print(f"  {a.ticker:5} {a.status:22} {a.detail[:110]}")
    print(f"Informe: {folder / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
