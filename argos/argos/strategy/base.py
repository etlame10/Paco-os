"""Motor de estrategias: contrato común para reglas que generan señales.

Una señal es HIPOTÉTICA: describe qué haría una regla en una fecha dada. Nunca
es una orden y no hay ningún camino en el código que la envíe a un broker.
Las señales se consumen por el backtesting (y, más adelante, por el paper
trading) para comprobar si una regla habría funcionado.

Para añadir una estrategia: subclase de `Strategy`, implementar
`generate_signals` y registrarla con `register_strategy`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import Any

import pandas as pd
from pydantic import BaseModel


class SignalAction(str, Enum):
    ENTER_LONG = "entrar_largo"
    EXIT = "salir"


class Signal(BaseModel):
    date: date
    action: SignalAction
    reason: str
    hypothetical: bool = True


class Strategy(ABC):
    name: str
    description: str

    def __init__(self, **params: Any):
        self.params = params

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """Recibe OHLCV indexado por fecha y devuelve señales ordenadas.

        Regla de oro anti-sesgo: la señal de la fecha t solo puede usar datos
        hasta t inclusive. El backtesting la ejecutará en t+1.
        """


_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str, **params: Any) -> Strategy:
    return _REGISTRY[name](**params)


def available_strategies() -> dict[str, str]:
    return {name: cls.description for name, cls in _REGISTRY.items()}
