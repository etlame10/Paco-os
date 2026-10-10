"""Motor de backtesting.

Recibe DATOS + SEÑALES + CONFIGURACIÓN y simula la cuenta sesión a sesión.
No sabe qué estrategia generó las señales: solo ve fechas y acciones.

Reglas de simulación (deliberadamente simples y explícitas):
  - Solo largos: o se está comprado, o en liquidez. Sin apalancamiento ni cortos.
  - Tamaño: todo el efectivo disponible en cada compra (se permiten fracciones de acción).
  - Ejecución: señal de la sesión t → apertura de la sesión t+1 (nunca antes).
  - Compra:  precio = apertura × (1 + slippage); comisión = precio × cantidad × comisión%.
  - Venta:   precio = apertura × (1 − slippage); comisión = precio × cantidad × comisión%.
  - Capital diario = efectivo + cantidad × cierre (valoración a mercado).
  - Señal de entrada estando comprado, o de salida estando en liquidez: se ignora y se anota.
  - Si `liquidate_at_end`, la posición abierta se vende al CIERRE de la última sesión, con costes.

Nada aquí envía órdenes: es aritmética sobre un histórico.
"""

from __future__ import annotations

import pandas as pd

from argos.backtest.models import (
    BacktestConfig,
    EquityPoint,
    IgnoredSignal,
    SimulationResult,
    Trade,
)
from argos.strategy.base import Signal, SignalAction

_EPS = 1e-9


class SimulationError(ValueError):
    pass


class Backtester:
    def simulate(self, df: pd.DataFrame, signals: list[Signal], config: BacktestConfig) -> SimulationResult:
        self._validate_inputs(df, signals)
        comm, slip = config.commission_pct, config.slippage_pct
        dates = [ts.date() for ts in df.index]
        opens = df["open"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        by_date = {s.date: s for s in signals}

        cash = config.initial_capital
        qty = 0.0
        open_trade: dict | None = None
        pending: Signal | None = None
        trades: list[Trade] = []
        ignored: list[IgnoredSignal] = []
        curve: list[EquityPoint] = []
        total_comm = total_slip = 0.0

        def close_position(i: int, ref_price: float, signal_date, reason: str) -> None:
            nonlocal cash, qty, open_trade, total_comm, total_slip
            price = ref_price * (1 - slip)
            gross = qty * price
            commission = gross * comm
            proceeds = gross - commission
            slip_cost = qty * (ref_price - price)
            cash += proceeds
            total_comm += commission
            total_slip += slip_cost
            t = open_trade
            pnl = proceeds - t["invested"]
            trades.append(Trade(
                entry_signal_date=t["signal_date"], entry_date=t["date"],
                entry_reference_price=t["ref"], entry_price=t["price"],
                exit_signal_date=signal_date, exit_date=dates[i],
                exit_reference_price=ref_price, exit_price=price, exit_reason=reason,
                quantity=qty, entry_commission=t["commission"], exit_commission=commission,
                slippage_cost=t["slip_cost"] + slip_cost, invested=t["invested"], proceeds=proceeds,
                pnl=pnl, return_pct=pnl / t["invested"], bars_held=i - t["index"],
            ))
            qty = 0.0
            open_trade = None

        for i, d in enumerate(dates):
            # 1) Ejecutar la señal pendiente de la sesión anterior, a la apertura de hoy.
            if pending is not None:
                if not pending.date < d:  # salvaguarda explícita (no un assert, que puede desactivarse)
                    raise SimulationError("Una operación no puede ejecutarse antes ni el mismo día que su señal.")
                ref = opens[i]
                if pending.action is SignalAction.ENTER_LONG:
                    price = ref * (1 + slip)
                    quantity = cash / (price * (1 + comm))
                    commission = quantity * price * comm
                    invested = quantity * price + commission
                    total_comm += commission
                    total_slip += quantity * (price - ref)
                    cash -= invested
                    if abs(cash) < _EPS * max(1.0, config.initial_capital):
                        cash = 0.0
                    qty = quantity
                    open_trade = dict(signal_date=pending.date, date=d, ref=ref, price=price,
                                      commission=commission, invested=invested,
                                      slip_cost=quantity * (price - ref), index=i)
                else:
                    close_position(i, ref, pending.date, "señal de salida")
                pending = None

            # 2) Valorar la cuenta al cierre.
            curve.append(EquityPoint(date=d, equity=cash + qty * closes[i], cash=cash,
                                     position_qty=qty, close=closes[i]))

            # 3) Leer la señal de hoy (calculada con datos hasta hoy) para ejecutarla mañana.
            sig = by_date.get(d)
            if sig is None:
                continue
            in_position = qty > 0
            if sig.action is SignalAction.ENTER_LONG and in_position:
                ignored.append(IgnoredSignal(signal=sig, reason="Ya había una posición abierta."))
            elif sig.action is SignalAction.EXIT and not in_position:
                ignored.append(IgnoredSignal(signal=sig, reason="No había posición que cerrar."))
            elif i == len(dates) - 1:
                ignored.append(IgnoredSignal(signal=sig, reason="Señal en la última sesión: no hay sesión siguiente para ejecutarla."))
            else:
                pending = sig

        if qty > 0 and config.liquidate_at_end:
            last = len(dates) - 1
            close_position(last, closes[last], None, "liquidación al final del periodo")
            curve[-1] = EquityPoint(date=dates[last], equity=cash, cash=cash, position_qty=0.0, close=closes[last])

        return SimulationResult(
            config=config, trades=trades, equity_curve=curve, ignored_signals=ignored,
            final_equity=curve[-1].equity, total_commission=total_comm, total_slippage=total_slip,
        )

    @staticmethod
    def _validate_inputs(df: pd.DataFrame, signals: list[Signal]) -> None:
        if df is None or df.empty:
            raise SimulationError("No hay datos que simular.")
        for col in ("open", "close"):
            if col not in df.columns:
                raise SimulationError(f"Faltan la columna '{col}'.")
        if not df.index.is_monotonic_increasing or df.index.has_duplicates:
            raise SimulationError("Las fechas deben estar ordenadas y sin duplicados.")
        if (df[["open", "close"]] <= 0).any().any() or df[["open", "close"]].isna().any().any():
            raise SimulationError("Hay precios vacíos o no positivos.")
        valid = {ts.date() for ts in df.index}
        seen = set()
        for s in signals:
            if s.date not in valid:
                raise SimulationError(f"Señal en una fecha sin datos: {s.date}.")
            if s.date in seen:
                raise SimulationError(f"Más de una señal el mismo día: {s.date}.")
            seen.add(s.date)
