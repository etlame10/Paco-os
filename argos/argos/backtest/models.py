"""Modelos del backtesting. Todo es SIMULACIÓN sobre datos históricos."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from argos.strategy.base import Signal

EXECUTION_RULE = (
    "Una señal calculada con el cierre de la sesión t se ejecuta a la APERTURA de la sesión t+1. "
    "Una señal en la última sesión no llega a ejecutarse."
)
HISTORICAL_WARNING = (
    "RESULTADO HISTÓRICO, NO PREDICCIÓN. Esto describe qué habría pasado en el pasado con estas "
    "reglas y supuestos. Los resultados históricos no garantizan resultados futuros."
)


class BacktestConfig(BaseModel):
    initial_capital: float = Field(10_000.0, gt=0, le=1e12)
    #: Comisión por operación, en tanto por uno sobre el importe (0.001 = 0,1%).
    commission_pct: float = Field(0.001, ge=0, le=0.05)
    #: Deslizamiento, en tanto por uno sobre el precio de referencia (0.0005 = 0,05%).
    slippage_pct: float = Field(0.0005, ge=0, le=0.05)
    start: date | None = None
    end: date | None = None
    #: Cerrar la posición abierta al final del periodo (al cierre de la última sesión, con costes).
    #: Así estrategia y Buy & Hold se comparan pagando ambas la salida.
    liquidate_at_end: bool = True

    @model_validator(mode="after")
    def _check_period(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError(f"La fecha de inicio ({self.start}) es posterior a la de fin ({self.end}).")
        return self


class Trade(BaseModel):
    """Una operación completa (compra + venta) con todos sus costes."""

    entry_signal_date: date
    entry_date: date
    entry_reference_price: float  # apertura de la sesión de ejecución
    entry_price: float  # precio efectivo tras deslizamiento
    exit_signal_date: date | None
    exit_date: date
    exit_reference_price: float
    exit_price: float
    exit_reason: str
    quantity: float
    entry_commission: float
    exit_commission: float
    slippage_cost: float
    invested: float  # efectivo que salió en la compra (precio × cantidad + comisión)
    proceeds: float  # efectivo que entró en la venta (precio × cantidad − comisión)
    pnl: float
    return_pct: float
    bars_held: int

    @field_validator("quantity")
    @classmethod
    def _positive(cls, v):
        if v <= 0:
            raise ValueError("La cantidad debe ser positiva.")
        return v


class IgnoredSignal(BaseModel):
    signal: Signal
    reason: str


class EquityPoint(BaseModel):
    date: date
    equity: float
    cash: float
    position_qty: float
    close: float


class SimulationResult(BaseModel):
    """Salida del motor: no contiene ninguna referencia a la estrategia."""

    config: BacktestConfig
    trades: list[Trade]
    equity_curve: list[EquityPoint]
    ignored_signals: list[IgnoredSignal]
    final_equity: float
    total_commission: float
    total_slippage: float


class PerformanceMetrics(BaseModel):
    initial_capital: float
    final_capital: float
    total_return: float
    annualized_return: float | None
    annualized_return_note: str | None = None
    max_drawdown: float
    volatility: float | None
    sharpe: float | None
    sharpe_note: str
    n_trades: int
    win_rate: float | None
    avg_trade_pnl: float | None
    avg_trade_return: float | None
    best_trade_return: float | None
    worst_trade_return: float | None
    exposure: float
    total_costs: float


class ComparisonItem(BaseModel):
    metric: str
    strategy: float | None
    benchmark: float | None
    difference: float | None
    better: bool | None  # None si no se puede comparar
    text: str


class Comparison(BaseModel):
    items: list[ComparisonItem]
    verdict: str
    caveats: list[str]


class LookAheadAudit(BaseModel):
    passed: bool
    checked_cutoffs: int
    method: str
    failures: list[str] = Field(default_factory=list)


class Transparency(BaseModel):
    data: dict
    strategy: dict
    commission: str
    slippage: str
    period: dict
    execution_rule: str
    position_sizing: str
    assumptions: list[str]


class BacktestLeg(BaseModel):
    """Resultado de una estrategia (ARGOS o Buy & Hold) en el periodo."""

    label: str
    signals: list[Signal]
    simulation: SimulationResult
    metrics: PerformanceMetrics


class BacktestReport(BaseModel):
    ticker: str
    is_simulated_data: bool
    kind: str = "resultado_historico"
    warning: str = HISTORICAL_WARNING
    transparency: Transparency
    strategy: BacktestLeg
    benchmark: BacktestLeg
    comparison: Comparison
    lookahead_audit: LookAheadAudit
    notes: list[str]
    live_trading_enabled: bool = False
