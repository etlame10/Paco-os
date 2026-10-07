"""Síntesis: convierte interpretaciones en una conclusión auditable.

No hay caja negra. La conclusión es la suma de factores visibles:
    contribución = peso del área × (+1 alcista, −1 bajista, 0 neutral)
    puntuación   = suma de contribuciones / suma de pesos  (entre −1 y +1)
La puntuación nunca se muestra sola: siempre va acompañada de la lista de
factores que la producen, y la etiqueta final indica también el riesgo.
"""

from __future__ import annotations

from argos.core.models import Conclusion, Factor, Interpretation, RiskAssessment, Stance
from argos.core.safety import DISCLAIMER

# Peso de cada área en la conclusión. Visibles y modificables a propósito:
# el backtesting servirá para comprobar si estos pesos tienen sentido.
AREA_WEIGHTS: dict[str, float] = {
    "tendencia": 1.0,
    "momentum": 1.0,
    "volumen": 0.5,
}

_SIGN = {Stance.BULLISH: 1, Stance.BEARISH: -1, Stance.NEUTRAL: 0}

# (puntuación mínima, etiqueta, sesgo)
_LABELS = [
    (0.6, "Escenario alcista", Stance.BULLISH),
    (0.2, "Escenario moderadamente alcista", Stance.BULLISH),
    (-0.2, "Escenario mixto / sin dirección clara", Stance.NEUTRAL),
    (-0.6, "Escenario moderadamente bajista", Stance.BEARISH),
    (-1.01, "Escenario bajista", Stance.BEARISH),
]


def synthesize(interpretations: list[Interpretation], risk: RiskAssessment) -> Conclusion:
    factors = [
        Factor(
            interpretation_id=i.id,
            area=i.area,
            statement=i.statement,
            stance=i.stance,
            weight=AREA_WEIGHTS[i.area],
            contribution=AREA_WEIGHTS[i.area] * _SIGN[i.stance],
        )
        for i in interpretations
        if i.area in AREA_WEIGHTS
    ]
    total_weight = sum(f.weight for f in factors)
    score = sum(f.contribution for f in factors) / total_weight if total_weight else 0.0
    label, stance = next((lbl, st) for threshold, lbl, st in _LABELS if score >= threshold)

    n_bull = sum(f.stance is Stance.BULLISH for f in factors)
    n_bear = sum(f.stance is Stance.BEARISH for f in factors)
    n_neu = len(factors) - n_bull - n_bear
    agreement = (
        f"{n_bull} factor(es) alcista(s), {n_bear} bajista(s) y {n_neu} neutral(es). "
        + ("Los factores apuntan en direcciones distintas: la conclusión es poco sólida."
           if n_bull and n_bear else "Los factores direccionales coinciden entre sí.")
    )
    risk_text = {
        "bajo": "con riesgo bajo",
        "moderado": "con riesgo moderado",
        "elevado": "pero con riesgo elevado",
        "muy elevado": "pero con riesgo muy elevado",
    }.get(risk.level, "con riesgo no evaluado")

    if not factors:
        label, stance = "Sin conclusión: datos insuficientes", Stance.NEUTRAL

    return Conclusion(
        label=label,
        stance=stance,
        summary=f"{label}, {risk_text}.",
        score=round(score, 3),
        score_method=(
            "Suma de contribuciones (peso del área × +1 alcista / −1 bajista / 0 neutral) "
            f"dividida entre la suma de pesos. Pesos: {AREA_WEIGHTS}. Rango: −1 a +1."
        ),
        factors=factors,
        risk_level=risk.level,
        agreement_note=agreement,
        disclaimer=DISCLAIMER,
    )
