"""Orquestación del backtest:

    DATOS → ESTRATEGIA → SEÑALES → BACKTESTER → RESULTADOS (+ Buy & Hold + comparación)

El servicio es el único que conoce ambas partes; el `Backtester` solo recibe señales.
"""

from __future__ import annotations

import pandas as pd

from argos.backtest.comparison import compare
from argos.backtest.engine import Backtester
from argos.backtest.lookahead import LookAheadError, audit_lookahead
from argos.backtest.metrics import compute_metrics
from argos.backtest.models import (
    EXECUTION_RULE,
    BacktestConfig,
    BacktestLeg,
    BacktestReport,
    Transparency,
)
from argos.core.safety import LIVE_TRADING_ENABLED
from argos.data.base import DataProviderError
from argos.data.normalize import normalize_history, normalize_ticker
from argos.data.registry import ProviderRegistry, default_registry
from argos.strategy import examples as _examples  # noqa: F401  (registra estrategias)
from argos.strategy.base import Strategy, get_strategy
from argos.strategy.examples import BuyAndHold

#: Sesiones mínimas dentro del periodo simulado.
MIN_PERIOD_BARS = 20


class InsufficientDataError(DataProviderError):
    pass


class BacktestService:
    def __init__(self, registry: ProviderRegistry | None = None, engine: Backtester | None = None):
        self.registry = registry or default_registry()
        self.engine = engine or Backtester()

    def run(self, raw_ticker: str, strategy_name: str, params: dict | None, config: BacktestConfig) -> BacktestReport:
        strategy = get_strategy(strategy_name, **(params or {}))
        return self.run_strategy(raw_ticker, strategy, config)

    def run_strategy(self, raw_ticker: str, strategy: Strategy, config: BacktestConfig) -> BacktestReport:
        # 1) DATOS
        ticker = normalize_ticker(raw_ticker)
        provider = self.registry.resolve(ticker)
        history = normalize_history(provider.get_price_history(ticker))
        df_all = history.to_dataframe()
        if df_all.empty:
            raise InsufficientDataError(f"{ticker}: no hay datos válidos.")
        first, last = df_all.index[0].date(), df_all.index[-1].date()

        start = config.start or first
        end = config.end or last
        if start > last or end < first:
            raise InsufficientDataError(
                f"El periodo {start} → {end} está fuera de los datos disponibles ({first} → {last})."
            )
        # La estrategia ve el histórico hasta el FIN del periodo (nunca después).
        # Los datos anteriores al inicio sirven para calentar indicadores; eso no es look-ahead.
        df_hist = df_all.loc[: pd.Timestamp(end)]
        df_period = df_hist.loc[pd.Timestamp(start):]
        if len(df_period) < MIN_PERIOD_BARS:
            raise InsufficientDataError(
                f"El periodo solo tiene {len(df_period)} sesiones; se necesitan al menos {MIN_PERIOD_BARS}."
            )
        if len(df_hist) < strategy.min_bars + 1:
            raise InsufficientDataError(
                f"{strategy.label} necesita {strategy.min_bars} sesiones de historia antes de su primera señal "
                f"y solo hay {len(df_hist)} hasta {end}."
            )

        # 2) ESTRATEGIA → SEÑALES (con auditoría anti look-ahead)
        audit = audit_lookahead(strategy, df_hist)
        if not audit.passed:
            raise LookAheadError("La estrategia usa información futura: " + " ".join(audit.failures[:3]))
        period_start = df_period.index[0].date()
        signals = [s for s in strategy.generate_signals(df_hist) if s.date >= period_start]

        # 3) BACKTESTER (no sabe qué estrategia es)
        sim = self.engine.simulate(df_period, signals, config)

        # 4) Referencia Buy & Hold, mismo motor, mismo periodo, mismos costes
        bh = BuyAndHold()
        bh_signals = bh.generate_signals(df_period)
        bh_sim = self.engine.simulate(df_period, bh_signals, config)

        metrics, bh_metrics = compute_metrics(sim), compute_metrics(bh_sim)
        simulated = history.provenance.is_simulated

        notes = list(history.normalization_notes)
        warm_idx = strategy.min_bars - 1
        if warm_idx < len(df_hist) and df_hist.index[warm_idx].date() > period_start:
            notes.append(
                f"La estrategia no puede emitir señales hasta {df_hist.index[warm_idx].date()} "
                f"(necesita {strategy.min_bars} sesiones de historia). Hasta entonces permanece en liquidez, "
                "mientras Buy & Hold ya está invertido."
            )
        if not signals:
            notes.append("La estrategia no generó ninguna señal en el periodo: permaneció en liquidez todo el tiempo.")
        if sim.ignored_signals:
            notes.append(f"{len(sim.ignored_signals)} señal(es) no se ejecutaron (ver detalle).")

        transparency = Transparency(
            data={
                "ticker": ticker,
                "provider": history.provenance.provider,
                "source": history.provenance.source_description,
                "is_simulated": simulated,
                "warning": history.provenance.warning,
                "available_from": first.isoformat(),
                "available_to": last.isoformat(),
                "bars_in_period": len(df_period),
                "bars_used_by_strategy": len(df_hist),
                "frequency": "diaria",
                "price_used": "apertura para ejecutar; cierre para señales y valoración",
            },
            strategy=strategy.describe(),
            commission=f"{config.commission_pct * 100:.3f}% del importe en cada compra y en cada venta",
            slippage=f"{config.slippage_pct * 100:.3f}% en contra sobre el precio de referencia en cada ejecución",
            period={
                "start": period_start.isoformat(),
                "end": df_period.index[-1].date().isoformat(),
                "requested_start": config.start.isoformat() if config.start else None,
                "requested_end": config.end.isoformat() if config.end else None,
            },
            execution_rule=EXECUTION_RULE,
            position_sizing="Todo el efectivo disponible en cada compra (se permiten fracciones). Solo largos, sin apalancamiento.",
            assumptions=[
                "Sin impuestos, dividendos ni intereses del efectivo.",
                "Siempre hay liquidez para ejecutar al precio de apertura (más deslizamiento).",
                "Buy & Hold compra en la apertura de la 2.ª sesión del periodo (misma regla de ejecución).",
                "Las posiciones abiertas se cierran al cierre de la última sesión, pagando costes."
                if config.liquidate_at_end else "Las posiciones abiertas se valoran al último cierre, sin costes de salida.",
            ],
        )
        return BacktestReport(
            ticker=ticker,
            is_simulated_data=simulated,
            transparency=transparency,
            strategy=BacktestLeg(label=strategy.label, signals=signals, simulation=sim, metrics=metrics),
            benchmark=BacktestLeg(label=bh.label, signals=bh_signals, simulation=bh_sim, metrics=bh_metrics),
            comparison=compare(metrics, bh_metrics, simulated_data=simulated),
            lookahead_audit=audit,
            notes=notes,
            live_trading_enabled=LIVE_TRADING_ENABLED,
        )
