"""Modelos del backtesting (preparados para la fase de simulación histórica)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    initial_capital: float = 10_000.0
    commission_pct: float = 0.001  # 0,1% por operación
    slippage_pct: float = 0.0005
    start: date | None = None
    end: date | None = None
    #: Las señales del día t se ejecutan a la apertura de t+1 (evita mirar al futuro).
    execution: str = "next_open"


class Trade(BaseModel):
    entry_date: date
    entry_price: float
    exit_date: date | None = None
    exit_price: float | None = None
    quantity: float

    @property
    def pnl(self) -> float | None:
        if self.exit_price is None:
            return None
        return (self.exit_price - self.entry_price) * self.quantity


class BacktestMetrics(BaseModel):
    total_return: float
    annualized_return: float | None
    max_drawdown: float
    volatility: float | None
    sharpe: float | None
    n_trades: int
    win_rate: float | None
    profit_loss: float


class BacktestResult(BaseModel):
    strategy: str
    params: dict
    ticker: str
    config: BacktestConfig
    equity_curve: list[tuple[date, float]] = Field(default_factory=list)
    trades: list[Trade] = Field(default_factory=list)
    metrics: BacktestMetrics
    is_simulated_data: bool
