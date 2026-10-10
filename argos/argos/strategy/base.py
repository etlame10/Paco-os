"""Motor de estrategias: contrato común para reglas que generan señales.

Una señal es HIPOTÉTICA: describe qué haría una regla en una fecha dada. Nunca
es una orden y no hay ningún camino en el código que la envíe a un broker.

Flujo:  DATOS → ESTRATEGIA → SEÑALES → BACKTESTER → RESULTADOS
La estrategia solo produce señales; el backtester solo consume señales y no
sabe qué estrategia las generó.

Para añadir una estrategia: subclase de `Strategy`, declarar `param_spec`,
implementar `min_bars` y `generate_signals`, y decorarla con `register_strategy`.
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


class ParamSpec(BaseModel):
    """Declaración de un parámetro: permite validarlo y generar la interfaz."""

    default: int
    min: int
    max: int
    description: str


class Strategy(ABC):
    name: str
    label: str
    description: str
    #: Parámetros configurables (todos enteros en esta fase).
    param_spec: dict[str, ParamSpec] = {}

    def __init__(self, **params: Any):
        unknown = set(params) - set(self.param_spec)
        if unknown:
            raise ValueError(f"Parámetros desconocidos para {self.name}: {sorted(unknown)}")
        resolved: dict[str, int] = {}
        for key, spec in self.param_spec.items():
            raw = params.get(key, spec.default)
            try:
                value = int(raw)
            except (TypeError, ValueError):
                raise ValueError(f"{key} debe ser un número entero (recibido {raw!r}).")
            if value != raw and not (isinstance(raw, str) and raw.strip() == str(value)):
                raise ValueError(f"{key} debe ser un número entero (recibido {raw!r}).")
            if not spec.min <= value <= spec.max:
                raise ValueError(f"{key} debe estar entre {spec.min} y {spec.max} (recibido {value}).")
            resolved[key] = value
        self.params = resolved
        self.validate()

    def validate(self) -> None:
        """Validaciones entre parámetros. Por defecto, ninguna."""

    @property
    @abstractmethod
    def min_bars(self) -> int:
        """Sesiones necesarias antes de que la estrategia pueda emitir su primera señal."""

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """Recibe OHLCV indexado por fecha y devuelve señales ordenadas por fecha.

        Regla anti look-ahead: la señal de la fecha t solo puede usar datos
        hasta t inclusive (el cierre de t ya se conoce al terminar la sesión).
        El backtester la ejecuta en la apertura de t+1. El backtesting verifica
        esta regla automáticamente en cada ejecución (ver backtest/lookahead.py).
        """

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "params": self.params,
            "min_bars": self.min_bars,
        }


_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str, **params: Any) -> Strategy:
    if name not in _REGISTRY:
        raise ValueError(f"Estrategia desconocida: {name!r}. Disponibles: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**params)


def available_strategies() -> dict[str, str]:
    return {name: cls.description for name, cls in _REGISTRY.items()}


def strategy_catalog() -> list[dict]:
    return [
        {
            "name": cls.name,
            "label": cls.label,
            "description": cls.description,
            "params": {k: v.model_dump() for k, v in cls.param_spec.items()},
        }
        for cls in _REGISTRY.values()
    ]
