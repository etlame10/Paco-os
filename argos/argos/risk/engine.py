"""Motor de riesgo: mide la incertidumbre histórica del activo.

Todo aquí describe el PASADO. Los escenarios proyectan rangos suponiendo que
la volatilidad histórica se mantiene, lo cual puede no ocurrir.
"""

from __future__ import annotations

import math

import pandas as pd

from argos.analysis.technical import indicators as ind
from argos.analysis.technical.analyzer import pct_abs
from argos.core.models import IndicatorValue, Interpretation, RiskAssessment, Scenario, Stance

# Umbrales de volatilidad anualizada. Son orientativos (un índice amplio suele
# moverse en torno al 15-20% anual; una acción individual, bastante más).
VOL_LEVELS = [(0.20, "bajo"), (0.35, "moderado"), (0.50, "elevado")]
VOL_MAX_LEVEL = "muy elevado"


def risk_level(vol: float | None) -> str:
    if vol is None:
        return "desconocido"
    for threshold, label in VOL_LEVELS:
        if vol < threshold:
            return label
    return VOL_MAX_LEVEL


class RiskEngine:
    def assess(self, df: pd.DataFrame) -> RiskAssessment:
        close = df["close"]
        price = float(close.iloc[-1])
        year = close.tail(ind.TRADING_DAYS)
        returns = ind.log_returns(close).dropna().tail(ind.TRADING_DAYS)

        vol20 = ind.annualized_volatility(close, 20)
        vol1y = ind.annualized_volatility(close, ind.TRADING_DAYS)
        mdd = ind.max_drawdown(year)
        cur_dd = float(ind.drawdown(year).iloc[-1])
        var95 = float(math.exp(returns.quantile(0.05)) - 1) if len(returns) >= 60 else None

        metrics = [
            IndicatorValue(id="vol_20d", name="Volatilidad 20 sesiones (anualizada)", value=_r(vol20), unit="%",
                           method="Desviación típica de los rendimientos logarítmicos diarios × √252."),
            IndicatorValue(id="vol_1y", name="Volatilidad 1 año (anualizada)", value=_r(vol1y), unit="%",
                           method="Igual que la anterior, sobre las últimas 252 sesiones."),
            IndicatorValue(id="max_drawdown_1y", name="Caída máxima 1 año", value=_r(mdd), unit="%",
                           method="Mayor caída desde un máximo previo dentro del último año."),
            IndicatorValue(id="current_drawdown", name="Caída actual desde máximos", value=_r(cur_dd), unit="%",
                           method="Último cierre respecto al máximo de cierre del último año."),
            IndicatorValue(id="var95_1d", name="VaR histórico 95% (1 día)", value=_r(var95), unit="%",
                           method="Percentil 5 de los rendimientos diarios del último año: en 1 de cada 20 "
                                  "sesiones la caída fue igual o peor."),
        ]

        level = risk_level(vol1y if vol1y is not None else vol20)
        interpretations: list[Interpretation] = []
        ref_vol = vol1y if vol1y is not None else vol20
        if ref_vol is not None:
            interpretations.append(Interpretation(
                id="risk_volatility",
                area="riesgo",
                statement=f"Volatilidad anualizada de {pct_abs(ref_vol, 0)}: riesgo {level}.",
                stance=Stance.NEUTRAL,
                rule="Volatilidad < 20% bajo · 20–35% moderado · 35–50% elevado · > 50% muy elevado.",
                evidence=["vol_1y" if vol1y is not None else "vol_20d"],
                caveat="La volatilidad cambia con el tiempo; los periodos de calma pueden terminar de golpe.",
            ))
        if vol20 is not None and vol1y is not None and vol20 > vol1y * 1.3:
            interpretations.append(Interpretation(
                id="risk_vol_rising",
                area="riesgo",
                statement="La volatilidad reciente es claramente superior a la media del año: el activo está más nervioso de lo habitual.",
                stance=Stance.NEUTRAL,
                rule="Volatilidad 20 sesiones > 1,3 × volatilidad 1 año.",
                evidence=["vol_20d", "vol_1y"],
            ))
        interpretations.append(Interpretation(
            id="risk_drawdown",
            area="riesgo",
            statement=f"En el último año llegó a caer {pct_abs(mdd)} desde un máximo; hoy está {pct_abs(cur_dd)} por debajo de su máximo.",
            stance=Stance.NEUTRAL,
            rule="Descripción directa de la caída máxima y la caída actual.",
            evidence=["max_drawdown_1y", "current_drawdown"],
            caveat="Una caída pasada no indica el tamaño de la próxima.",
        ))

        scenarios = []
        if ref_vol is not None:
            horizon = 21
            sigma = ref_vol * math.sqrt(horizon / ind.TRADING_DAYS)
            for k, name, prob in ((1, "Rango habitual a 1 mes", "≈ 2 de cada 3"), (2, "Rango amplio a 1 mes", "≈ 19 de cada 20")):
                scenarios.append(Scenario(
                    name=name,
                    description=(
                        f"Si la volatilidad se mantuviera, {prob} meses el precio terminaría "
                        f"entre {price * math.exp(-k * sigma):.2f} y {price * math.exp(k * sigma):.2f}."
                    ),
                    low=round(price * math.exp(-k * sigma), 2),
                    high=round(price * math.exp(k * sigma), 2),
                    basis=f"±{k}σ con σ mensual = volatilidad anual × √(21/252). Supone rendimientos "
                          "aproximadamente normales; las caídas extremas son más frecuentes en la realidad. "
                          "No es una predicción.",
                ))
        return RiskAssessment(level=level, metrics=metrics, interpretations=interpretations, scenarios=scenarios)


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)
