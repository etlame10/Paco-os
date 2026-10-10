"""Ejecutor de EXP-002 (GEM con capital bajo frente a referencias pasivas), según protocols/EXP-002.json.

    python -m argos.experiments.exp002                     # comprobación previa: bloqueo y ficheros. No simula.
    python -m argos.experiments.exp002 --ensayo-sintetico  # ENSAYO con datos SIMULADOS. Nunca cuenta como resultado.
    python -m argos.experiments.exp002 --ejecutar          # experimento real (requiere autorización expresa)

Datos: data/csv/EXP-002/ (nunca data/csv/, que es de EXP-001). Resultados y registro: data/experiments/EXP-002/.
Las decisiones de detalle que el protocolo no fija literalmente están en INTERPRETATIONS y salen en el informe.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np

from argos import __version__
from argos.backtest.portfolio import (
    CostModel,
    Execution,
    InsufficientCashError,
    Market,
    PortfolioRun,
    PriceDataError,
    calendar_year_returns,
    cagr,
    excess_returns,
    max_drawdown,
    monthly_returns,
    sharpe_excess,
    simulate,
    sortino_excess,
    volatility,
)
from argos.data.base import DataProviderError
from argos.data.calendar_us import sessions as nyse_sessions
from argos.data.providers.csv_provider import CsvProvider
from argos.data.quality import QualityRequirements, assess_quality
from argos.experiments.protocol import Protocol, ProtocolChangedError, check_preregistered, load_protocol
from argos.experiments.registry import file_sha256, git_commit
from argos.experiments.storage import csv_dir_for, results_dir_for
from argos.strategy.gem import BILLS, BONDS, EXUS, GEM_TICKERS, US, Decision, gem_decisions

EXPERIMENT_ID = "EXP-002"
C1_FACTOR = 0.75
EXPECTED_EVAL_DECISIONS = 132
BOOT_REPLICAS, BOOT_BLOCK, BOOT_SEED = 10_000, 12, 20261009
PORTFOLIOS = ("gem", "spy_buy_hold", "pasiva_30_30_40")
MIX_WEIGHTS = {US: 0.30, EXUS: 0.30, BONDS: 0.40}

#: Puntos que el protocolo no fija al pie de la letra y cómo se han resuelto. Se publican en el informe.
INTERPRETATIONS = [
    "Sharpe y Sortino diarios: e_1 usa V_0 = C0 y el cierre de BIL de la sesión anterior al tramo (dato pasado).",
    "ΔSharpe del bootstrap: Sharpe mensual EN EXCESO sobre BIL (como todos los Sharpe del protocolo); BIL se "
    "remuestrea con los mismos bloques que las carteras.",
    "Bootstrap: un generador nuevo default_rng(20261009) para cada comparación (frente a SPY y frente a 30/30/40), "
    "para que cada intervalo sea reproducible por separado.",
    "Peor año y regímenes: solo años naturales COMPLETOS dentro del tramo.",
    "Volatilidad anualizada: desviación típica (ddof = 1) de los rendimientos diarios de V × √252.",
    "S8 (ejecución al cierre): la entrada inicial sigue la regla del tramo (primera apertura). Si la última decisión "
    "coincide con la última sesión, se ejecuta al cierre y a continuación se liquida (lectura literal).",
    "insufficient_cash_rule y comprobaciones contables: un fallo en cualquier configuración o tramo deja inconcluso "
    "el experimento entero ('en algún momento').",
]

#: Variantes de protocols/EXP-002.json (sensitivity.variants). Un test comprueba que coinciden con el protocolo.
VARIANT_CHANGES: dict[str, dict] = {
    "principal": {},
    "S1": {"variant": "S1"},
    "S2": {"lookback": 6},
    "S3": {"lookback": 9},
    "S4": {"min_commission": 2.0, "slippage": 0.0010},
    "S5": {"capital": 50.0},
    "S6": {"capital": 200.0},
    "S7": {"capital": 10_000.0},
    "S8": {"timing": "close"},
}


class Exp002Error(RuntimeError):
    pass


class InconclusiveError(Exp002Error):
    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class Config:
    id: str
    variant: str = "principal"
    lookback: int = 12
    min_commission: float = 1.0
    slippage: float = 0.0005
    commission_pct: float = 0.0
    capital: float = 100.0
    timing: str = "open"

    @property
    def costs(self) -> CostModel:
        return CostModel(self.min_commission, self.slippage, self.commission_pct)


def load_raw_protocol(path: Path) -> dict:
    """El JSON completo del protocolo: el modelo Protocol no conserva los campos propios de EXP-002."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def configs_from_protocol(protocol: Protocol, raw: dict) -> list[Config]:
    ids = ["principal"] + [v["id"] for v in raw["sensitivity"]["variants"]]
    if ids != list(VARIANT_CHANGES):
        raise Exp002Error(f"Las variantes del protocolo {ids} no coinciden con las implementadas {list(VARIANT_CHANGES)}.")
    c = protocol.costs
    base = Config("principal", lookback=int(protocol.strategy["params"]["lookback_months"]),
                  min_commission=float(c["commission_min_per_order"]), slippage=float(c["slippage_pct"]),
                  commission_pct=float(c["commission_pct"]), capital=float(c["initial_capital"]))
    return [replace(base, id=k, **v) for k, v in VARIANT_CHANGES.items()]


# ------------------------------------------------------------------ datos


@dataclass
class AssetData:
    ticker: str
    file: str
    sha256: str | None
    simulated: bool
    rows: int
    first: date | None
    last: date | None
    quality: str
    audit: str = "no ejecutada"
    notes: list[str] = field(default_factory=list)


def load_market(protocol: Protocol, csv_dir: Path, ticker_files: dict[str, str] | None = None,
                raw_dir: Path | None = None, audit: bool = True) -> tuple[Market, list[AssetData]]:
    """Lee los cuatro CSV, aplica el control de calidad y la regla de calendario. Nunca rellena ni corrige."""
    req = protocol.data_requirements
    start, end = date.fromisoformat(req["required_start"]), date.fromisoformat(req["required_end"])
    requirements = QualityRequirements(required_start=start, required_end=end,
                                       max_start_tolerance_days=req.get("max_start_tolerance_days", 10),
                                       min_years=req.get("min_years"))
    expected = nyse_sessions(start, end)
    provider = CsvProvider(csv_dir)
    problems: list[str] = []
    info: list[AssetData] = []
    series: dict[str, dict[date, tuple[float, float]]] = {}
    for t in GEM_TICKERS:
        fname = (ticker_files or {}).get(t, t)
        path = Path(csv_dir) / f"{fname}.csv"
        try:
            hist = provider.get_price_history(fname)
        except DataProviderError as exc:
            problems.append(f"{t}: {exc}")
            continue
        q = assess_quality(hist, requirements)
        a = AssetData(t, path.name, file_sha256(path), hist.provenance.is_simulated, len(hist.bars),
                      hist.bars[0].date if hist.bars else None, hist.bars[-1].date if hist.bars else None, q.status)
        info.append(a)
        if q.blocked:
            problems.append(f"{t}: bloqueado por el control de calidad ({q.summary()}).")
        if audit:
            from argos.data import audit as audit_mod

            au = audit_mod.audit_csv(t, path, (expected[0], end))
            if raw_dir is not None and au.rows:
                audit_mod.audit_provenance(au, raw_dir)
            a.audit = au.status
            if au.status == audit_mod.FAIL:
                bad = [f"{c.label}: {c.detail}" for c in au.checks if c.status == audit_mod.FAIL]
                problems.append(f"{t}: la auditoría falla ({'; '.join(bad)[:300]}).")
        dates = [b.date for b in hist.bars]
        outside = [d for d in dates if d < start or d > end]
        if outside:
            problems.append(f"{t}: {len(outside)} filas fuera de {start} → {end} (p. ej. {outside[0]}); "
                            "el protocolo no permite usarlas (incluida la reserva desde 2026-10-01).")
        extra = sorted(set(dates) - set(expected))
        missing = sorted(set(expected) - set(dates))
        if extra:
            problems.append(f"{t}: calendario incorrecto, {len(extra)} fechas que no son sesión NYSE (p. ej. {extra[0]}).")
        if missing:
            problems.append(f"{t}: faltan {len(missing)} sesiones NYSE esperadas (p. ej. {missing[0]}). No se rellenan.")
        series[t] = {b.date: (b.open, b.close) for b in hist.bars}
    if problems:
        raise InconclusiveError(problems)
    days = tuple(expected)
    try:
        market = Market(days, {t: np.array([series[t][d][0] for d in days]) for t in GEM_TICKERS},
                        {t: np.array([series[t][d][1] for d in days]) for t in GEM_TICKERS})
    except PriceDataError as exc:
        raise InconclusiveError([f"Precios no válidos: {exc}"]) from None
    return market, info


# ------------------------------------------------------------------ simulación por tramo


@dataclass
class PeriodRun:
    name: str
    first_index: int
    last_index: int
    initial_decision: Decision
    executed_decisions: list[Decision]
    runs: dict[str, PortfolioRun]

    @property
    def decisions_count(self) -> int:
        return 1 + len(self.executed_decisions)


def period_bounds(market: Market, start: date, end: date) -> tuple[int, int]:
    idx = [i for i, d in enumerate(market.sessions) if start <= d <= end]
    if not idx:
        raise InconclusiveError([f"No hay sesiones entre {start} y {end}."])
    if idx[0] == 0:
        raise InconclusiveError([f"El tramo {start} → {end} empieza en la primera sesión de los datos: falta la "
                                 "sesión anterior (decisión previa y cierre de BIL)."])
    return idx[0], idx[-1]


def run_period(market: Market, decisions: list[Decision], name: str, start: date, end: date, cfg: Config) -> PeriodRun:
    first, last = period_bounds(market, start, end)
    prior = [d for d in decisions if d.index < first]
    if not prior:
        raise InconclusiveError([f"{name}: no hay ninguna decisión GEM anterior al inicio ({market.sessions[first]})."])
    initial = prior[-1]
    execs = [Execution(first, {initial.target: 1.0}, "open", "entrada", initial.date)]
    executed = []
    for d in decisions:
        if not (first <= d.index <= last):
            continue
        i = d.index + 1 if cfg.timing == "open" else d.index
        if i > last:
            continue  # su ejecución caería después de la última sesión: no se ejecuta
        executed.append(d)
        execs.append(Execution(i, {d.target: 1.0}, cfg.timing, "cambio", d.date))
    costs = cfg.costs
    runs = {
        "gem": simulate(market, execs, costs, cfg.capital, first, last),
        "spy_buy_hold": simulate(market, [Execution(first, {US: 1.0}, "open", "entrada")], costs, cfg.capital, first, last),
        "pasiva_30_30_40": simulate(market, [Execution(first, dict(MIX_WEIGHTS), "open", "entrada")], costs,
                                    cfg.capital, first, last),
    }
    return PeriodRun(name, first, last, initial, executed, runs)


def bil_slice(market: Market, pr: PeriodRun) -> np.ndarray:
    return market.closes[BILLS][pr.first_index - 1: pr.last_index + 1]


def portfolio_metrics(market: Market, pr: PeriodRun, key: str) -> dict:
    run = pr.runs[key]
    e = excess_returns(run.values, bil_slice(market, pr))
    years = calendar_year_returns(run.dates, run.values)
    complete = {y: r for y, (r, ok) in years.items() if ok}
    worst = min(complete.items(), key=lambda kv: kv[1]) if complete else None
    held = Counter(t for h in run.holdings for t in h)
    n = len(run.holdings)
    return {
        "final_value": run.final_value,
        "total_return": run.final_value / run.initial_capital - 1,
        "cagr": cagr(run.initial_capital, run.final_value, run.dates[0], run.dates[-1]),
        "max_drawdown": max_drawdown(run.values),
        "volatility": volatility(run.values),
        "sharpe_excess": sharpe_excess(e),
        "sortino_excess": sortino_excess(e),
        "worst_complete_year": {"year": worst[0], "return": worst[1]} if worst else None,
        "orders": len(run.orders),
        "switches": run.switches,
        "commissions": run.commissions,
        "slippage": run.slippage,
        "total_cost_over_capital": (run.commissions + run.slippage) / run.initial_capital,
        "fraction_of_sessions": {t: held[t] / n for t in sorted(held)},
    }


def accounting_problems(market: Market, pr: PeriodRun, cfg: Config) -> list[str]:
    """Comprobaciones contables de metrics.accounting_checks y decisions_vs_trades."""
    out = []
    expected_orders = {"gem": 2 + 2 * pr.runs["gem"].switches, "spy_buy_hold": 2, "pasiva_30_30_40": 6}
    for key, run in pr.runs.items():
        tag = f"{cfg.id}/{pr.name}/{key}"
        if len(run.orders) != expected_orders[key]:
            out.append(f"{tag}: {len(run.orders)} órdenes, se esperaban {expected_orders[key]}.")
        for o in run.orders:
            gross = o.quantity * o.reference_price * (1 - cfg.slippage)
            c = cfg.costs.sell_commission(gross) if o.side == "venta" else None
            if c is not None and not math.isclose(o.commission, c, rel_tol=0, abs_tol=1e-12):
                out.append(f"{tag}: comisión de venta {o.commission} ≠ {c} el {o.date}.")
            if o.side == "compra" and cfg.commission_pct == 0 and o.commission != cfg.min_commission:
                out.append(f"{tag}: comisión de compra {o.commission} ≠ {cfg.min_commission} el {o.date}.")
            if not math.isclose(o.slippage_cost, o.quantity * o.reference_price * cfg.slippage, rel_tol=1e-12, abs_tol=1e-12):
                out.append(f"{tag}: deslizamiento mal calculado el {o.date}.")
        if cfg.commission_pct == 0 and not math.isclose(run.commissions, len(run.orders) * cfg.min_commission, abs_tol=1e-9):
            out.append(f"{tag}: comisión total {run.commissions} ≠ órdenes × m.")
        gap = run.accounting_identity_gap()
        if abs(gap) >= 0.005:
            out.append(f"{tag}: la identidad V_T = C0 + bruto − comisiones − deslizamiento no cuadra ({gap:+.6f}).")
        if any(BILLS in h for h in run.holdings):
            out.append(f"{tag}: BIL aparece en cartera; el protocolo dice que nunca se compra.")
    # Ejecución en la sesión prevista: apertura siguiente a la decisión (o su cierre en S8).
    for o in pr.runs["gem"].orders:
        if o.kind != "cambio" or o.decision_date is None:
            continue
        di = market.index_of(o.decision_date)
        want = market.sessions[di + 1] if cfg.timing == "open" else market.sessions[di]
        if o.date != want or o.timing != cfg.timing:
            out.append(f"{cfg.id}/{pr.name}: orden del {o.date} ({o.timing}) para la decisión del {o.decision_date}; "
                       f"se esperaba {want} ({cfg.timing}).")
    k = pr.runs["gem"].switches
    if not (0 <= k <= pr.decisions_count):
        out.append(f"{cfg.id}/{pr.name}: K = {k} fuera de 0..{pr.decisions_count}.")
    return out


# ------------------------------------------------------------------ información futura


def lookahead_audit(market: Market, cfg: Config) -> dict:
    """Recalcula cada decisión con los datos TRUNCADOS en su propio día: debe salir idéntica."""
    full = gem_decisions(market, cfg.lookback, cfg.variant)
    mismatches = []
    for d in full:
        seen = gem_decisions(market.truncated(d.index), cfg.lookback, cfg.variant)
        if not seen or seen[-1] != d:
            mismatches.append(str(d.date))
    return {"config": cfg.id, "checked": len(full), "mismatches": mismatches, "ok": not mismatches}


# ------------------------------------------------------------------ incertidumbre


def block_bootstrap(r_a: np.ndarray, r_b: np.ndarray, r_bil: np.ndarray, replicas: int = BOOT_REPLICAS,
                    block: int = BOOT_BLOCK, seed: int = BOOT_SEED) -> dict:
    """Bootstrap circular por bloques sobre rendimientos mensuales EMPAREJADOS. IC del 95% por percentiles."""
    n = len(r_a)
    if not (len(r_b) == len(r_bil) == n) or n < 2 * block:
        raise Exp002Error(f"Series mensuales no válidas para el bootstrap (n = {n}).")
    rng = np.random.default_rng(seed)
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(replicas, nb))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(replicas, nb * block)[:, :n]

    def stats(r, rb):
        grow = np.prod(1 + r, axis=1)
        c = grow ** (12 / n) - 1
        e = r - rb
        sh = e.mean(axis=1) / e.std(axis=1, ddof=1) * math.sqrt(12)
        curve = np.concatenate([np.ones((r.shape[0], 1)), np.cumprod(1 + r, axis=1)], axis=1)
        mdd = np.max(1 - curve / np.maximum.accumulate(curve, axis=1), axis=1)
        return c, sh, mdd

    ca, sa, ma = stats(r_a[idx], r_bil[idx])
    cb, sb, mb = stats(r_b[idx], r_bil[idx])

    def ci(x):
        lo, hi = np.percentile(x, [2.5, 97.5])
        return {"low": float(lo), "high": float(hi)}

    return {"months": n, "replicas": replicas, "block": block, "seed": seed,
            "delta_cagr": ci(ca - cb), "delta_sharpe": ci(sa - sb), "delta_max_drawdown": ci(ma - mb)}


def monthly_series(market: Market, pr: PeriodRun) -> dict[str, np.ndarray]:
    out = {k: monthly_returns(r.dates, r.values) for k, r in pr.runs.items()}
    out["bil"] = monthly_returns(pr.runs["gem"].dates, list(bil_slice(market, pr)))
    return out


# ------------------------------------------------------------------ experimento completo


def evaluate(market: Market, protocol: Protocol, raw: dict) -> dict:
    """Simula configuración principal y variantes en los tres tramos y evalúa los criterios del protocolo."""
    configs = configs_from_protocol(protocol, raw)
    periods = [(p.name, p.start, p.end) for p in protocol.periods]
    inconclusive: list[str] = []
    results: dict[str, dict] = {}
    runs: dict[tuple[str, str], PeriodRun] = {}
    audits = []
    for cfg in configs:
        decisions = gem_decisions(market, cfg.lookback, cfg.variant)
        if cfg.id in ("principal", "S1", "S2", "S3"):
            audits.append(lookahead_audit(market, cfg))
        results[cfg.id] = {"config": asdict(cfg), "periods": {}}
        for name, start, end in periods:
            try:
                pr = run_period(market, decisions, name, start, end, cfg)
            except InsufficientCashError as exc:
                inconclusive.append(f"{cfg.id}/{name}: {exc}")
                continue
            runs[(cfg.id, name)] = pr
            problems = accounting_problems(market, pr, cfg)
            inconclusive += problems
            results[cfg.id]["periods"][name] = {
                "first_session": str(market.sessions[pr.first_index]), "last_session": str(market.sessions[pr.last_index]),
                "sessions": pr.last_index - pr.first_index + 1,
                "initial_decision": str(pr.initial_decision.date), "decisions": pr.decisions_count,
                "switches_K": pr.runs["gem"].switches, "gem_orders": len(pr.runs["gem"].orders),
                "metrics": {k: portfolio_metrics(market, pr, k) for k in PORTFOLIOS},
                "accounting_ok": not problems,
            }
    for a in audits:
        if not a["ok"]:
            inconclusive.append(f"Auditoría anti look-ahead de {a['config']}: decisiones distintas en {a['mismatches'][:5]}.")

    def crit(cfg_id: str) -> dict | None:
        p = results.get(cfg_id, {}).get("periods", {}).get("evaluacion")
        if not p:
            return None
        m = p["metrics"]
        mdd_g, mdd_s = m["gem"]["max_drawdown"], m["spy_buy_hold"]["max_drawdown"]
        cg, cm = m["gem"]["cagr"], m["pasiva_30_30_40"]["cagr"]
        return {"C1": mdd_g <= C1_FACTOR * mdd_s, "C2": cg is not None and cm is not None and cg >= cm,
                "maxdd_gem": mdd_g, "maxdd_spy": mdd_s, "maxdd_ratio": mdd_g / mdd_s if mdd_s else None,
                "cagr_gem": cg, "cagr_mix": cm, "cagr_spy": m["spy_buy_hold"]["cagr"]}

    main, s4 = crit("principal"), crit("S4")
    boot = {}
    if ("principal", "evaluacion") in runs:
        ms = monthly_series(market, runs[("principal", "evaluacion")])
        boot = {"vs_pasiva_30_30_40": block_bootstrap(ms["gem"], ms["pasiva_30_30_40"], ms["bil"]),
                "vs_spy_buy_hold": block_bootstrap(ms["gem"], ms["spy_buy_hold"], ms["bil"])}
        n_dec = results["principal"]["periods"]["evaluacion"]["decisions"]
        if n_dec != EXPECTED_EVAL_DECISIONS:
            inconclusive.append(f"Decisiones en el periodo de evaluación: {n_dec}, el protocolo exige {EXPECTED_EVAL_DECISIONS}.")
    else:
        inconclusive.append("No se pudo simular la configuración principal en el periodo de evaluación.")

    if inconclusive or main is None:
        verdict = "inconcluso"
    elif not (main["C1"] and main["C2"]):
        verdict = "no_se_ha_demostrado_mejora"
    elif boot["vs_pasiva_30_30_40"]["delta_cagr"]["low"] > 0 and s4 and s4["C1"] and s4["C2"]:
        verdict = "mejora_robusta"
    else:
        verdict = "indicio_no_concluyente"
    return {"configs": results, "criteria": {"principal": main, "S4": s4}, "bootstrap": boot,
            "lookahead": audits, "regimes": regimes(runs.get(("principal", "evaluacion")), protocol),
            "verdict": verdict, "inconclusive_reasons": inconclusive,
            "trials_count": raw["metrics"]["trials_count"], "interpretations": INTERPRETATIONS}


def regimes(pr: PeriodRun | None, protocol: Protocol) -> list[dict]:
    if pr is None:
        return []
    bull, bear = protocol.regime_classification["bull_threshold"], protocol.regime_classification["bear_threshold"]
    years = {k: calendar_year_returns(r.dates, r.values) for k, r in pr.runs.items()}
    out = []
    for y, (spy, complete) in years["spy_buy_hold"].items():
        if not complete:
            continue
        reg = "alcista" if spy > bull else "bajista" if spy < bear else "lateral"
        out.append({"year": y, "regime": reg, **{k: years[k][y][0] for k in PORTFOLIOS}})
    return out


# ------------------------------------------------------------------ registro, informe y CLI


def check_registry_lock(registry_path: Path, sha: str) -> None:
    if not registry_path.is_file():
        return
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if not rec.get("dry_run") and rec.get("protocol_sha256") != sha:
            raise ProtocolChangedError("EXP-002 ha cambiado después de registrar resultados reales. Crea EXP-003.")


def run_exp002(*, csv_dir: Path | None = None, results_dir: Path | None = None, raw_dir: Path | None = None,
               dry_run: bool, ticker_files: dict[str, str] | None = None, protocol_dir: Path | None = None) -> dict:
    protocol, sha, ppath = load_protocol(EXPERIMENT_ID, protocol_dir)
    check_preregistered(EXPERIMENT_ID, sha, protocol_dir)
    results_dir = Path(results_dir) if results_dir is not None else results_dir_for(EXPERIMENT_ID)
    registry_path = results_dir / "registry.jsonl"
    check_registry_lock(registry_path, sha)
    csv_dir = Path(csv_dir) if csv_dir is not None else csv_dir_for(EXPERIMENT_ID)
    if raw_dir is None and not dry_run:
        from argos.data.sources import tiingo

        raw_dir = tiingo.RAW_DIR
    out = {"experiment_id": EXPERIMENT_ID, "protocol_sha256": sha, "registered_at": str(protocol.registered_at),
           "dry_run": dry_run, "argos_version": __version__, "git_commit": git_commit(),
           "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "csv_dir": str(csv_dir), "data": []}
    try:
        market, info = load_market(protocol, csv_dir, ticker_files, raw_dir=None if dry_run else raw_dir)
        out["data"] = [asdict(a) for a in info]
        if not dry_run and any(a.simulated for a in info):
            raise InconclusiveError(["Hay ficheros SIMULADOS (DEMO-*) en un experimento real; el protocolo lo prohíbe."])
        out.update(evaluate(market, protocol, load_raw_protocol(ppath)))
    except InconclusiveError as exc:
        out.update({"verdict": "inconcluso", "inconclusive_reasons": exc.reasons, "interpretations": INTERPRETATIONS})
    folder = results_dir / ("ensayos" if dry_run else "resultados") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (folder / "report.md").write_text(render_report(out), encoding="utf-8")
    with registry_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({k: out.get(k) for k in ("experiment_id", "protocol_sha256", "dry_run", "argos_version",
                                                     "git_commit", "run_at", "verdict")}
                            | {"data": [{"ticker": d["ticker"], "file": d["file"], "sha256": d["sha256"]} for d in out["data"]],
                               "folder": str(folder)}, ensure_ascii=False) + "\n")
    out["folder"] = str(folder)
    return out


def _p(x) -> str:
    return "—" if x is None else f"{x * 100:.2f}%"


def _n(x) -> str:
    return "—" if x is None else f"{x:.2f}"


VERDICT_TEXT = {
    "mejora_robusta": "En esta muestra histórica GEM cumplió C1 y C2, con intervalo de ΔCAGR por encima de 0 y también "
                      "con costes ×2. Es evidencia en esta muestra, no una garantía ni una recomendación.",
    "indicio_no_concluyente": "En esta muestra histórica GEM cumplió C1 y C2, pero no las demás condiciones de mejora "
                              "robusta. Es un indicio, no una conclusión.",
    "no_se_ha_demostrado_mejora": "En esta muestra histórica GEM no cumplió C1 o C2: no se ha demostrado una mejora.",
    "inconcluso": "El experimento es INCONCLUSO: no se pudo evaluar conforme al protocolo (ver motivos).",
}


def render_report(r: dict) -> str:
    L: list[str] = []
    a = L.append
    if r["dry_run"]:
        a("# ENSAYO CON DATOS SIMULADOS — EXP-002\n")
        a("> **Esto no es el experimento.** Los precios son inventados; el resultado no dice nada sobre GEM ni sobre "
          "ningún mercado real. Solo comprueba que el procedimiento funciona de principio a fin.\n")
    else:
        a("# EXP-002 — GEM con capital bajo frente a referencias pasivas\n")
        a("> Resultado histórico, no una predicción ni una recomendación.\n")
    a(f"- Protocolo `protocols/EXP-002.json` (registrado el {r['registered_at']}) · SHA-256 `{r['protocol_sha256']}`")
    a(f"- ARGOS {r['argos_version']} · commit `{r['git_commit']}` · ejecutado {r['run_at']} · datos `{r['csv_dir']}`")
    a(f"- {r.get('trials_count', 'Pruebas acumuladas: —')}\n")
    a("## Datos\n\n| Activo | Fichero | SHA-256 | Sesiones | Desde | Hasta | Calidad | Auditoría | Simulado |")
    a("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for d in r["data"]:
        a(f"| {d['ticker']} | {d['file']} | `{(d['sha256'] or '—')[:16]}…` | {d['rows']} | {d['first']} | {d['last']} | "
          f"{d['quality']} | {d['audit']} | {'SÍ' if d['simulated'] else 'no'} |")
    text = VERDICT_TEXT[r["verdict"]]
    if r["dry_run"]:
        text = ("ENSAYO: el veredicto se calcula solo para comprobar el procedimiento y NO tiene ningún valor. "
                + text.replace("En esta muestra histórica", "Con estos datos simulados"))
    a(f"\n## Veredicto: `{r['verdict']}`\n\n{text}\n")
    if r.get("inconclusive_reasons"):
        a("Motivos:\n" + "\n".join(f"- {x}" for x in r["inconclusive_reasons"]) + "\n")
    crit = (r.get("criteria") or {}).get("principal")
    if crit:
        a("## Criterios (periodo de evaluación, configuración principal)\n")
        a(f"- **C1** MaxDD(GEM) ≤ 0,75 × MaxDD(SPY): {_p(crit['maxdd_gem'])} frente a 0,75 × {_p(crit['maxdd_spy'])} "
          f"(razón {_n(crit['maxdd_ratio'])}) → **{'se cumple' if crit['C1'] else 'no se cumple'}**. "
          "Umbral EXPLORATORIO, elegido conociendo el periodo; no está validado estadísticamente.")
        a(f"- **C2** CAGR(GEM) ≥ CAGR(30/30/40): {_p(crit['cagr_gem'])} frente a {_p(crit['cagr_mix'])} → "
          f"**{'se cumple' if crit['C2'] else 'no se cumple'}**.")
        s4 = r["criteria"].get("S4")
        if s4:
            a(f"- Con costes ×2 (S4): C1 {'sí' if s4['C1'] else 'no'}, C2 {'sí' if s4['C2'] else 'no'}.")
        for k, b in r.get("bootstrap", {}).items():
            a(f"- Bootstrap {k} ({b['months']} meses, {b['replicas']} réplicas, bloque {b['block']}, semilla {b['seed']}): "
              f"IC 95% ΔCAGR [{_p(b['delta_cagr']['low'])}, {_p(b['delta_cagr']['high'])}], "
              f"ΔSharpe [{_n(b['delta_sharpe']['low'])}, {_n(b['delta_sharpe']['high'])}], "
              f"ΔMaxDD [{_p(b['delta_max_drawdown']['low'])}, {_p(b['delta_max_drawdown']['high'])}].")
        a("")
    for cid, c in (r.get("configs") or {}).items():
        if cid != "principal":
            continue
        for name, p in c["periods"].items():
            a(f"## Tramo `{name}` ({p['first_session']} → {p['last_session']}, {p['sessions']} sesiones)\n")
            a(f"Decisiones: {p['decisions']} (la primera, del {p['initial_decision']}, fija la entrada) · cambios K = "
              f"{p['switches_K']} · órdenes de GEM = {p['gem_orders']} (= 2 + 2K). Las decisiones no son operaciones.\n")
            a("| Cartera | Valor final | CAGR | MaxDD | Volatilidad | Sharpe exc. | Sortino exc. | Peor año | Órdenes | Costes/C0 |")
            a("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
            for k in PORTFOLIOS:
                m = p["metrics"][k]
                w = m["worst_complete_year"]
                a(f"| {k} | {m['final_value']:.2f} | {_p(m['cagr'])} | {_p(m['max_drawdown'])} | {_p(m['volatility'])} | "
                  f"{_n(m['sharpe_excess'])} | {_n(m['sortino_excess'])} | "
                  f"{(str(w['year']) + ' ' + _p(w['return'])) if w else '—'} | {m['orders']} | {_p(m['total_cost_over_capital'])} |")
            a("")
    if r.get("configs"):
        a("## Variantes de sensibilidad (periodo de evaluación)\n")
        a("Se publican todas. **Ninguna sustituye a la configuración principal ni cambia el veredicto.**\n")
        a("| Config. | CAGR GEM | MaxDD GEM | Sharpe exc. GEM | K | CAGR 30/30/40 | MaxDD SPY | C1 | C2 |")
        a("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for cid, c in r["configs"].items():
            p = c["periods"].get("evaluacion")
            if not p:
                a(f"| {cid} | no simulado | | | | | | | |")
                continue
            m = p["metrics"]
            c1 = m["gem"]["max_drawdown"] <= C1_FACTOR * m["spy_buy_hold"]["max_drawdown"]
            c2 = (m["gem"]["cagr"] or -9) >= (m["pasiva_30_30_40"]["cagr"] or 9)
            a(f"| {cid} | {_p(m['gem']['cagr'])} | {_p(m['gem']['max_drawdown'])} | {_n(m['gem']['sharpe_excess'])} | "
              f"{p['switches_K']} | {_p(m['pasiva_30_30_40']['cagr'])} | {_p(m['spy_buy_hold']['max_drawdown'])} | "
              f"{'sí' if c1 else 'no'} | {'sí' if c2 else 'no'} |")
        a("")
    if r.get("regimes"):
        a("## Años naturales completos del periodo de evaluación (régimen según SPY)\n")
        a("| Año | Régimen | GEM | SPY | 30/30/40 |\n| --- | --- | --- | --- | --- |")
        for y in r["regimes"]:
            a(f"| {y['year']} | {y['regime']} | {_p(y['gem'])} | {_p(y['spy_buy_hold'])} | {_p(y['pasiva_30_30_40'])} |")
        a("")
    if r.get("lookahead"):
        a("## Controles\n")
        for au in r["lookahead"]:
            a(f"- Anti look-ahead ({au['config']}): {au['checked']} decisiones recalculadas con datos truncados → "
              f"{'idénticas' if au['ok'] else 'DISTINTAS: ' + ', '.join(au['mismatches'][:5])}.")
        a("")
    a("## Interpretaciones de detalle\n")
    a("\n".join(f"- {x}" for x in r.get("interpretations", INTERPRETATIONS)))
    a("\n## Limitaciones\n")
    a("- 100 USD con 1 USD por orden: NO representa una inversión de 100 EUR (sin tipo de cambio, sin impuestos).")
    a("- Fracciones de participación: supuesto exclusivo de la simulación; no se afirma que un broker las permita.")
    a("- La regla principal de GEM no está verificada en el libro; S1 es la alternativa de fuentes secundarias.")
    a("- 2015–2025 es fuera de muestra para la regla, no para el diseño del experimento.")
    a("- ETF de EE. UU. como sustitutos de los índices del autor. Muestra pequeña de cambios de activo.")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ ensayo con datos simulados


def write_synthetic_dataset(protocol: Protocol, directory: Path, seed: int = 2002) -> dict[str, str]:
    """CSV DEMO-<TICKER>.csv con precios INVENTADOS en las sesiones NYSE del protocolo. Solo para ensayos y tests."""
    req = protocol.data_requirements
    days = nyse_sessions(date.fromisoformat(req["required_start"]), date.fromisoformat(req["required_end"]))
    rng = random.Random(seed)
    params = {US: (0.0004, 0.012), EXUS: (0.0002, 0.013), BONDS: (0.0001, 0.003), BILLS: (0.00005, 0.0002)}
    regime, mapping = 1.0, {}
    paths = {t: [] for t in GEM_TICKERS}
    price = {t: 100.0 for t in GEM_TICKERS}
    for i, _ in enumerate(days):
        if i % 500 == 0:
            regime = rng.choice([1.0, 1.0, 1.0, -1.0])
        for t, (mu, sd) in params.items():
            drift = mu * (regime if t in (US, EXUS) else 1.0)
            o = price[t] * math.exp(rng.gauss(0, sd / 4))
            c = o * math.exp(rng.gauss(drift, sd))
            paths[t].append((o, c))
            price[t] = c
    directory.mkdir(parents=True, exist_ok=True)
    for t in GEM_TICKERS:
        name = f"DEMO-{t}"
        lines = ["date,open,high,low,close,volume"]
        for d, (o, c) in zip(days, paths[t]):
            lines.append(f"{d},{o:.6f},{max(o, c) * 1.002:.6f},{min(o, c) * 0.998:.6f},{c:.6f},1000000")
        (directory / f"{name}.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        mapping[t] = name
    return mapping


def preflight(csv_dir: Path) -> list[str]:
    lines = []
    protocol, sha, _ = load_protocol(EXPERIMENT_ID)
    check_preregistered(EXPERIMENT_ID, sha)
    lines.append(f"Protocolo EXP-002 bloqueado: SHA-256 {sha} coincide con LOCKS.json.")
    lines.append(f"Carpeta de datos de EXP-002: {csv_dir}")
    for t in GEM_TICKERS:
        p = csv_dir / f"{t}.csv"
        lines.append(f"  {t}: " + (f"presente · SHA-256 {file_sha256(p)[:16]}…" if p.is_file() else "FALTA"))
    lines.append("No se ha simulado nada. Para el experimento real hace falta --ejecutar (y la autorización del usuario).")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m argos.experiments.exp002", description="Ejecutor de EXP-002.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ensayo-sintetico", action="store_true", help="Ensayo con datos SIMULADOS. Nunca cuenta.")
    g.add_argument("--ejecutar", action="store_true", help="Experimento REAL con data/csv/EXP-002/.")
    ap.add_argument("--resultados", type=Path, default=None, help="Carpeta de resultados (por defecto data/experiments/EXP-002/).")
    args = ap.parse_args(argv)
    try:
        if args.ensayo_sintetico:
            import tempfile

            protocol, _, _ = load_protocol(EXPERIMENT_ID)
            tmp = Path(tempfile.mkdtemp(prefix="argos-exp002-ensayo-"))
            mapping = write_synthetic_dataset(protocol, tmp)
            r = run_exp002(csv_dir=tmp, results_dir=args.resultados, dry_run=True, ticker_files=mapping)
        elif args.ejecutar:
            r = run_exp002(results_dir=args.resultados, dry_run=False)
        else:
            print("\n".join(preflight(csv_dir_for(EXPERIMENT_ID))))
            return 0
    except (ProtocolChangedError, FileNotFoundError, Exp002Error) as exc:
        print(f"✕ {exc}")
        return 2
    print(f"{'ENSAYO (datos simulados)' if r['dry_run'] else 'EXP-002'}: veredicto {r['verdict']}. Informe: {r['folder']}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
