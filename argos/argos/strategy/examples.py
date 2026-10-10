"""Estrategias de ejemplo. Sirven de referencia y de comparación, no de recomendación."""

from __future__ import annotations

import pandas as pd

from argos.analysis.technical.indicators import sma
from argos.strategy.base import ParamSpec, Signal, SignalAction, Strategy, register_strategy


@register_strategy
class BuyAndHold(Strategy):
    name = "buy_and_hold"
    label = "Buy & Hold"
    description = "Compra el primer día y mantiene. Referencia mínima que cualquier estrategia debe batir."

    @property
    def min_bars(self) -> int:
        return 1

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        if df.empty:
            return []
        return [Signal(date=df.index[0].date(), action=SignalAction.ENTER_LONG, reason="Inicio del periodo")]


@register_strategy
class SmaCrossover(Strategy):
    name = "sma_crossover"
    label = "Cruce de medias móviles"
    description = (
        "Señal de entrada cuando la media rápida cruza POR ENCIMA de la lenta; señal de salida cuando "
        "cruza POR DEBAJO. Solo posiciones largas (comprado o en liquidez). Solo actúa en los cruces: "
        "si al empezar ya está la rápida por encima, espera al siguiente cruce."
    )
    param_spec = {
        "fast": ParamSpec(default=50, min=2, max=400, description="Sesiones de la media rápida"),
        "slow": ParamSpec(default=200, min=3, max=400, description="Sesiones de la media lenta"),
    }

    def validate(self) -> None:
        if self.params["fast"] >= self.params["slow"]:
            raise ValueError("La media rápida debe ser más corta que la lenta.")

    @property
    def min_bars(self) -> int:
        # La media lenta necesita `slow` sesiones; el primer CRUCE requiere una sesión previa válida.
        return self.params["slow"] + 1

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        fast, slow = self.params["fast"], self.params["slow"]
        fast_ma = sma(df["close"], fast)
        slow_ma = sma(df["close"], slow)
        signals: list[Signal] = []
        prev: bool | None = None
        for ts, f, s in zip(df.index, fast_ma, slow_ma):
            if pd.isna(f) or pd.isna(s):
                continue
            state = bool(f > s)
            if prev is not None and state != prev:
                signals.append(Signal(
                    date=ts.date(),
                    action=SignalAction.ENTER_LONG if state else SignalAction.EXIT,
                    reason=(
                        f"SMA{fast} ({f:.2f}) cruza {'por encima' if state else 'por debajo'} "
                        f"de SMA{slow} ({s:.2f}) al cierre"
                    ),
                ))
            prev = state
        return signals
