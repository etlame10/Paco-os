"""Motor de carteras con pesos objetivo (EXP-002).

Recibe un MERCADO (sesiones comunes con aperturas y cierres ajustados de varios activos), una lista de
EJECUCIONES (en qué sesión y a qué precio pasar a qué pesos objetivo) y unos COSTES, y simula la cuenta.
No sabe qué estrategia generó las ejecuciones: GEM, comprar y mantener y la 30/30/40 usan el mismo motor.

Reglas (las de protocols/EXP-002.json):
  - Comisión por orden: c = max(m, p × importe). En una compra con efectivo asignado A, el importe es A − c,
    así que c = max(m, p·A/(1+p)) (solución exacta de c = max(m, p·(A − c))). En EXP-002 p = 0 y c = m.
  - Compra:  cantidad = (A − c) / (P × (1 + s)).     Venta: ingreso = cantidad × P × (1 − s) − c.
  - Deslizamiento registrado en cada orden: cantidad × P × s.
  - Una ejecución solo genera órdenes si el CONJUNTO de activos objetivo difiere del que hay en cartera:
    entonces se vende todo y se compra el objetivo con todo el efectivo (presupuesto = efectivo − n·c, repartido
    según los pesos). Si coincide, no hay orden.
  - Si el efectivo disponible para una compra es ≤ c, se detiene (InsufficientCashError). Nunca se fuerza.
  - Curva: V_0 = capital antes de la primera sesión; V_t al cierre de cada sesión, después de las ejecuciones
    de esa sesión; en la última sesión, V_T = efectivo tras liquidar al cierre con costes.

Nada aquí envía órdenes: es aritmética sobre un histórico.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

import numpy as np

Timing = Literal["open", "close"]
TRADING_DAYS = 252


class PortfolioError(ValueError):
    pass


class PriceDataError(PortfolioError):
    pass


class InsufficientCashError(PortfolioError):
    pass


@dataclass(frozen=True)
class Market:
    """Sesiones comunes y precios AJUSTADOS alineados por activo. Se valida al crearlo."""

    sessions: tuple[date, ...]
    opens: dict[str, np.ndarray]
    closes: dict[str, np.ndarray]

    def __post_init__(self):
        n = len(self.sessions)
        if n == 0:
            raise PriceDataError("El mercado no tiene ninguna sesión.")
        if any(b <= a for a, b in zip(self.sessions, self.sessions[1:])):
            raise PriceDataError("Las sesiones deben estar en orden estrictamente creciente y sin duplicados.")
        if set(self.opens) != set(self.closes):
            raise PriceDataError("Aperturas y cierres deben cubrir los mismos activos.")
        for kind, table in (("apertura", self.opens), ("cierre", self.closes)):
            for t, arr in table.items():
                if len(arr) != n:
                    raise PriceDataError(f"{t}: {len(arr)} precios de {kind} para {n} sesiones.")
                bad = ~(np.isfinite(arr) & (arr > 0))
                if bad.any():
                    i = int(np.argmax(bad))
                    raise PriceDataError(f"{t}: precio de {kind} no válido ({arr[i]!r}) el {self.sessions[i]}.")

    @property
    def tickers(self) -> list[str]:
        return sorted(self.opens)

    def index_of(self, d: date) -> int:
        try:
            return self.sessions.index(d)
        except ValueError:
            raise PortfolioError(f"{d} no es una sesión del mercado.") from None

    def truncated(self, last_index: int) -> "Market":
        """Mercado visto hasta la sesión last_index incluida (para auditar el uso de información futura)."""
        k = last_index + 1
        return Market(self.sessions[:k], {t: a[:k] for t, a in self.opens.items()},
                      {t: a[:k] for t, a in self.closes.items()})


@dataclass(frozen=True)
class CostModel:
    min_commission: float  # m
    slippage: float  # s
    commission_pct: float = 0.0  # p

    def __post_init__(self):
        if self.min_commission < 0 or self.slippage < 0 or self.commission_pct < 0 or self.slippage >= 1:
            raise PortfolioError("Costes no válidos.")

    def buy_commission(self, allocated: float) -> float:
        p = self.commission_pct
        return max(self.min_commission, p * allocated / (1 + p))

    def sell_commission(self, proceeds_gross: float) -> float:
        return max(self.min_commission, self.commission_pct * proceeds_gross)


@dataclass(frozen=True)
class Execution:
    """Pasar a `weights` en la sesión `index`, al precio de apertura o de cierre."""

    index: int
    weights: dict[str, float]
    timing: Timing = "open"
    reason: str = "cambio"  # "entrada" | "cambio"
    decision_date: date | None = None


@dataclass
class Order:
    date: date
    ticker: str
    side: Literal["compra", "venta"]
    kind: str  # "entrada" | "cambio" | "liquidación"
    timing: Timing
    quantity: float
    reference_price: float
    execution_price: float
    commission: float
    slippage_cost: float
    cash_after: float
    decision_date: date | None = None


@dataclass
class PortfolioRun:
    initial_capital: float
    start_index: int
    end_index: int
    dates: list[date]  # sesiones del tramo (t = 1..T)
    values: list[float]  # V_0, V_1, ..., V_T  (len = len(dates) + 1)
    holdings: list[frozenset[str]]  # activos en cartera al cierre de cada sesión, antes de la liquidación final
    orders: list[Order] = field(default_factory=list)
    gross_market_result: float = 0.0
    switches: int = 0  # ejecuciones que cambiaron el conjunto de activos, sin contar la entrada

    @property
    def final_value(self) -> float:
        return self.values[-1]

    @property
    def commissions(self) -> float:
        return sum(o.commission for o in self.orders)

    @property
    def slippage(self) -> float:
        return sum(o.slippage_cost for o in self.orders)

    def accounting_identity_gap(self) -> float:
        """V_T − (C0 + Σ resultado bruto − Σ comisiones − Σ deslizamiento). Debe ser ~0."""
        return self.final_value - (self.initial_capital + self.gross_market_result - self.commissions - self.slippage)


def _validate_weights(w: dict[str, float], market: Market) -> None:
    if not w:
        raise PortfolioError("Pesos objetivo vacíos.")
    unknown = set(w) - set(market.opens)
    if unknown:
        raise PortfolioError(f"Activos sin precios: {sorted(unknown)}.")
    if any(not (v > 0) for v in w.values()) or not math.isclose(sum(w.values()), 1.0, abs_tol=1e-12):
        raise PortfolioError(f"Los pesos deben ser positivos y sumar 1: {w}.")


def simulate(
    market: Market,
    executions: list[Execution],
    costs: CostModel,
    capital: float,
    start_index: int,
    end_index: int,
) -> PortfolioRun:
    """Simula las sesiones start_index..end_index (incluidas) y liquida al cierre de end_index."""
    if not (0 <= start_index <= end_index < len(market.sessions)):
        raise PortfolioError(f"Tramo de sesiones no válido: {start_index}..{end_index}.")
    if not (capital > 0):
        raise PortfolioError("El capital inicial debe ser positivo.")
    by_slot: dict[tuple[int, Timing], Execution] = {}
    for ex in executions:
        if not (start_index <= ex.index <= end_index):
            raise PortfolioError(f"Ejecución fuera del tramo: sesión {ex.index}.")
        _validate_weights(ex.weights, market)
        key = (ex.index, ex.timing)
        if key in by_slot:
            raise PortfolioError(f"Dos ejecuciones en la misma sesión y momento ({market.sessions[ex.index]}).")
        by_slot[key] = ex

    cash = float(capital)
    pos: dict[str, float] = {}
    basis: dict[str, float] = {}  # cantidad × precio de referencia de compra
    run = PortfolioRun(initial_capital=float(capital), start_index=start_index, end_index=end_index,
                       dates=[], values=[float(capital)], holdings=[])

    def sell_all(i: int, prices: dict[str, np.ndarray], timing: Timing, kind: str, decision: date | None) -> None:
        nonlocal cash
        for t in sorted(pos):
            q = pos.pop(t)
            ref = float(prices[t][i])
            gross = q * ref * (1 - costs.slippage)
            c = costs.sell_commission(gross)
            cash += gross - c
            run.gross_market_result += q * ref - basis.pop(t)
            run.orders.append(Order(market.sessions[i], t, "venta", kind, timing, q, ref, ref * (1 - costs.slippage),
                                    c, q * ref * costs.slippage, cash, decision))

    def apply(ex: Execution, i: int) -> None:
        nonlocal cash
        target = frozenset(ex.weights)
        if target == frozenset(pos):
            return
        prices = market.opens if ex.timing == "open" else market.closes
        had_position = bool(pos)
        sell_all(i, prices, ex.timing, ex.reason, ex.decision_date)
        if had_position:
            run.switches += 1
        n = len(ex.weights)
        commissions = [costs.buy_commission(cash * w) for w in ex.weights.values()]
        budget = cash - sum(commissions)
        for (t, w), c in zip(sorted(ex.weights.items()), commissions):
            allocated = budget * w + c
            if allocated <= c or budget <= 0:
                raise InsufficientCashError(
                    f"{market.sessions[i]}: efectivo disponible para comprar {t} ({allocated:.6f}) ≤ comisión ({c}). "
                    "El protocolo prohíbe forzar la orden: el experimento es inconcluso.")
            ref = float(prices[t][i])
            px = ref * (1 + costs.slippage)
            q = (allocated - c) / px
            cash -= allocated
            pos[t] = q
            basis[t] = q * ref
            run.orders.append(Order(market.sessions[i], t, "compra", ex.reason, ex.timing, q, ref, px, c,
                                    q * ref * costs.slippage, cash, ex.decision_date))
        if n and abs(cash) < 1e-9:
            cash = 0.0

    for i in range(start_index, end_index + 1):
        if (ex := by_slot.get((i, "open"))) is not None:
            apply(ex, i)
        if (ex := by_slot.get((i, "close"))) is not None:
            apply(ex, i)
        run.dates.append(market.sessions[i])
        run.holdings.append(frozenset(pos))
        if i == end_index:
            sell_all(i, market.closes, "close", "liquidación", None)
            if cash <= 0:
                raise InsufficientCashError(f"Valor final no positivo ({cash:.6f}) tras liquidar: inconcluso.")
            run.values.append(cash)
        else:
            run.values.append(cash + sum(q * float(market.closes[t][i]) for t, q in pos.items()))
    return run


# ------------------------------------------------------------------ métricas (definiciones del protocolo)


def max_drawdown(values: list[float] | np.ndarray) -> float:
    """MaxDD = max_t (1 − V_t / max(V_0..V_t)), con DD_0 = 0. Fracción positiva."""
    v = np.asarray(values, dtype=float)
    peaks = np.maximum.accumulate(v)
    return float(np.max(1 - v / peaks))


def cagr(initial: float, final: float, first: date, last: date) -> float | None:
    """(V_T / C0)^(365,25 / D) − 1, D = días naturales entre la primera y la última sesión."""
    days = (last - first).days
    if days <= 0 or initial <= 0 or final <= 0:
        return None
    return float((final / initial) ** (365.25 / days) - 1)


def excess_returns(values: list[float], bil_closes: np.ndarray) -> np.ndarray:
    """e_t = (V_t/V_{t−1} − 1) − (BIL_t/BIL_{t−1} − 1), t = 1..T.

    `bil_closes` son los cierres de BIL en la sesión ANTERIOR al tramo y en cada sesión del tramo (T + 1 valores).
    """
    v = np.asarray(values, dtype=float)
    b = np.asarray(bil_closes, dtype=float)
    if len(b) != len(v):
        raise PortfolioError("Hacen falta T + 1 cierres de BIL para T sesiones.")
    return (v[1:] / v[:-1] - 1) - (b[1:] / b[:-1] - 1)


def sharpe_excess(e: np.ndarray, periods_per_year: int = TRADING_DAYS) -> float | None:
    if len(e) < 2:
        return None
    sd = float(np.std(e, ddof=1))
    if sd == 0 or not math.isfinite(sd):
        return None
    return float(np.mean(e) / sd * math.sqrt(periods_per_year))


def sortino_excess(e: np.ndarray, periods_per_year: int = TRADING_DAYS) -> float | None:
    if len(e) < 2:
        return None
    dd = math.sqrt(float(np.mean(np.minimum(e, 0) ** 2)))
    if dd == 0:
        return None
    return float(np.mean(e) / dd * math.sqrt(periods_per_year))


def volatility(values: list[float]) -> float | None:
    v = np.asarray(values, dtype=float)
    r = v[1:] / v[:-1] - 1
    if len(r) < 2:
        return None
    return float(np.std(r, ddof=1) * math.sqrt(TRADING_DAYS))


def period_end_values(dates: list[date], values: list[float], key) -> list[tuple[object, float]]:
    """Último V de cada grupo (mes o año) en el tramo. `values[0]` es V_0 y `values[k]` corresponde a dates[k−1]."""
    out: dict[object, float] = {}
    for d, v in zip(dates, values[1:]):
        out[key(d)] = v
    return list(out.items())


def calendar_year_returns(dates: list[date], values: list[float]) -> dict[int, tuple[float, bool]]:
    """{año: (rentabilidad, completo)}. Base del primer año: V_0. Un año es completo si el tramo cubre
    desde su primera hasta su última sesión NYSE."""
    from argos.data.calendar_us import sessions

    ends = period_end_values(dates, values, key=lambda d: d.year)
    out, prev = {}, values[0]
    for year, v in ends:
        cal = sessions(date(year, 1, 1), date(year, 12, 31))
        complete = dates[0] <= cal[0] and dates[-1] >= cal[-1]
        out[year] = (v / prev - 1, complete)
        prev = v
    return out


def monthly_returns(dates: list[date], values: list[float]) -> np.ndarray:
    ends = period_end_values(dates, values, key=lambda d: (d.year, d.month))
    v = np.array([values[0]] + [x for _, x in ends], dtype=float)
    return v[1:] / v[:-1] - 1
