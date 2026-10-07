"""Motor de backtesting — contrato definido, implementación en la próxima fase.

Diseño previsto:
  1. Obtener histórico con cualquier `MarketDataProvider` (el mismo que usa el análisis).
  2. Pedir señales a una `Strategy` (solo puede usar datos hasta cada fecha).
  3. Simular la ejecución en la apertura siguiente, con comisión y deslizamiento.
  4. Construir la curva de capital y la lista de `Trade`.
  5. Calcular métricas con `argos.backtest.metrics.compute_metrics`.
  6. `compare()` ejecuta varias estrategias (siempre incluida Buy & Hold) sobre
     el mismo activo y periodos, para comparar en igualdad de condiciones.

Todo es simulación sobre datos históricos: no interviene ningún broker.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from argos.backtest.models import BacktestConfig, BacktestResult
from argos.core.models import PriceHistory
from argos.strategy.base import Strategy


class BacktestEngine(ABC):
    @abstractmethod
    def run(self, strategy: Strategy, history: PriceHistory, config: BacktestConfig) -> BacktestResult: ...

    def compare(
        self, strategies: list[Strategy], history: PriceHistory, config: BacktestConfig
    ) -> list[BacktestResult]:
        from argos.strategy.examples import BuyAndHold

        if not any(isinstance(s, BuyAndHold) for s in strategies):
            strategies = [BuyAndHold(), *strategies]
        return [self.run(s, history, config) for s in strategies]
