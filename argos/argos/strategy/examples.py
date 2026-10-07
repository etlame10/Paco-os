"""Estrategias de ejemplo. Sirven de referencia y de comparación, no de recomendación."""

from __future__ import annotations

import pandas as pd

from argos.analysis.technical.indicators import sma
from argos.strategy.base import Signal, SignalAction, Strategy, register_strategy


@register_strategy
class BuyAndHold(Strategy):
    name = "buy_and_hold"
    description = "Compra el primer día y mantiene. Referencia mínima que cualquier estrategia debe batir."

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if df.empty:
            return []
        return [Signal(date=df.index[0].date(), action=SignalAction.ENTER_LONG, reason="Inicio del periodo")]


@register_strategy
class SmaCrossover(Strategy):
    name = "sma_crossover"
    description = "Entra cuando la media rápida cruza por encima de la lenta y sale en el cruce contrario."

    def __init__(self, fast: int = 50, slow: int = 200):
        if fast >= slow:
            raise ValueError("La media rápida debe ser más corta que la lenta.")
        super().__init__(fast=fast, slow=slow)

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        fast, slow = self.params["fast"], self.params["slow"]
        above = (sma(df["close"], fast) > sma(df["close"], slow)).where(
            sma(df["close"], slow).notna()
        )
        signals: list[Signal] = []
        prev = None
        for ts, state in above.items():
            if pd.isna(state):
                continue
            state = bool(state)
            if prev is not None and state != prev:
                signals.append(Signal(
                    date=ts.date(),
                    action=SignalAction.ENTER_LONG if state else SignalAction.EXIT,
                    reason=f"SMA{fast} cruza {'por encima' if state else 'por debajo'} de SMA{slow}",
                ))
            prev = state
        return signals
