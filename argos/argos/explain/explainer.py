"""Capa de explicación: convierte el análisis estructurado en lenguaje natural.

Regla fundamental para cualquier explicador (presente o futuro, incluido uno
basado en un modelo de lenguaje): SOLO puede reformular lo que ya está en el
análisis estructurado. No puede añadir datos, cifras ni hechos nuevos. Por eso
recibe los objetos ya calculados y no tiene acceso a fuentes de datos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from argos.core.models import (
    AssetInfo,
    Conclusion,
    Explanation,
    ExplanationSection,
    Interpretation,
    Provenance,
    RiskAssessment,
    Stance,
)


class Explainer(ABC):
    name: str

    @abstractmethod
    def explain(
        self,
        asset: AssetInfo,
        provenance: Provenance,
        interpretations: list[Interpretation],
        risk: RiskAssessment,
        conclusion: Conclusion,
    ) -> Explanation: ...


class TemplateExplainer(Explainer):
    """Explicador determinista basado en plantillas: no inventa nada."""

    name = "plantillas (determinista)"

    def explain(self, asset, provenance, interpretations, risk, conclusion) -> Explanation:
        by_area: dict[str, list[Interpretation]] = {}
        for i in interpretations:
            by_area.setdefault(i.area, []).append(i)

        trend = by_area.get("tendencia", [])
        trend_word = _majority(trend)
        situation = (
            f"{asset.name} ({asset.ticker}) muestra una tendencia {trend_word} según sus medias móviles."
            if trend else f"No hay histórico suficiente para valorar la tendencia de {asset.ticker}."
        )
        if provenance.is_simulated:
            situation = "⚠ Análisis sobre DATOS SIMULADOS de un activo ficticio. " + situation

        tech_parts = [i.statement for area in ("tendencia", "momentum", "volumen", "soportes y resistencias")
                      for i in by_area.get(area, [])]

        why_lines = []
        for f in sorted(conclusion.factors, key=lambda f: -abs(f.contribution)):
            sign = {Stance.BULLISH: "suma", Stance.BEARISH: "resta", Stance.NEUTRAL: "no suma ni resta"}[f.stance]
            why_lines.append(f"• [{f.area}] {f.statement} → {sign} (peso {f.weight:g}).")
        why = (
            "La conclusión sale de sumar estos factores, de mayor a menor influencia:\n"
            + "\n".join(why_lines)
            + f"\nPuntuación resultante: {conclusion.score:+.2f} (escala −1 a +1). {conclusion.agreement_note}"
        )

        limits = (
            "Este análisis solo usa precios y volumen. Todavía no tiene en cuenta resultados "
            "empresariales, valoración, deuda, noticias ni contexto macroeconómico. Las reglas y "
            "umbrales son convenciones del análisis técnico que aún no se han validado con "
            "backtesting. " + conclusion.disclaimer
        )

        sections = [
            ExplanationSection(title="Situación", text=situation),
            ExplanationSection(title="Análisis técnico", text=" ".join(tech_parts) or "Sin datos suficientes."),
            ExplanationSection(
                title="Riesgo",
                text=" ".join(i.statement for i in risk.interpretations)
                + (" " + risk.scenarios[0].description if risk.scenarios else ""),
            ),
            ExplanationSection(title="Conclusión", text=conclusion.summary),
            ExplanationSection(title="Por qué", text=why),
            ExplanationSection(title="Qué NO sabemos", text=limits),
        ]
        return Explanation(
            generator=self.name,
            method_note="Texto generado con plantillas a partir de las interpretaciones; no añade información nueva.",
            sections=sections,
        )


def _majority(items: list[Interpretation]) -> str:
    bull = sum(i.stance is Stance.BULLISH for i in items)
    bear = sum(i.stance is Stance.BEARISH for i in items)
    if bull and not bear:
        return "alcista"
    if bear and not bull:
        return "bajista"
    return "mixta" if bull or bear else "indefinida"
