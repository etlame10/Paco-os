"""Análisis técnico: calcula indicadores y los interpreta con reglas explícitas.

Cada interpretación lleva:
  - `rule`: la regla aplicada, en lenguaje llano.
  - `evidence`: los ids de los indicadores que la sustentan.
  - `caveat`: el límite conocido de esa regla.
Los umbrales son convenciones habituales del análisis técnico, no verdades;
están aquí, a la vista, para poder discutirlos y validarlos con backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from argos.analysis.technical import indicators as ind
from argos.analysis.technical.levels import support_resistance
from argos.core.models import DataPoint, IndicatorValue, Interpretation, Stance


@dataclass
class TechnicalResult:
    data: list[DataPoint]
    indicators: list[IndicatorValue]
    interpretations: list[Interpretation]


def pct(x: float | None, digits: int = 1) -> str:
    return "n/d" if x is None else f"{x * 100:+.{digits}f}%"


def pct_abs(x: float | None, digits: int = 1) -> str:
    return "n/d" if x is None else f"{abs(x) * 100:.{digits}f}%"


def _round(x: float | None, digits: int = 4) -> float | None:
    return None if x is None else round(x, digits)


class TechnicalAnalyzer:
    def analyze(self, df: pd.DataFrame) -> TechnicalResult:
        close = df["close"]
        price = float(close.iloc[-1])
        year = df.tail(ind.TRADING_DAYS)

        data = [
            DataPoint(id="last_close", label="Último cierre", value=round(price, 4)),
            DataPoint(id="last_date", label="Fecha del último dato", value=df.index[-1].date().isoformat()),
            DataPoint(id="first_date", label="Primer dato disponible", value=df.index[0].date().isoformat()),
            DataPoint(id="n_bars", label="Sesiones disponibles", value=len(df)),
            DataPoint(id="high_52w", label="Máximo 52 semanas", value=round(float(year["high"].max()), 4)),
            DataPoint(id="low_52w", label="Mínimo 52 semanas", value=round(float(year["low"].min()), 4)),
            DataPoint(id="last_volume", label="Volumen última sesión", value=float(df["volume"].iloc[-1])),
        ]

        m = ind.macd(close)
        levels = support_resistance(df)
        vol20 = ind.sma(df["volume"], 20).iloc[-1]
        vol60 = ind.sma(df["volume"], 60).iloc[-1]
        volume_ratio = None if pd.isna(vol20) or pd.isna(vol60) or vol60 == 0 else float(vol20 / vol60)
        atr14 = ind.last(ind.atr(df, 14))
        high_52w = float(year["high"].max())

        values = {
            "sma20": ind.last(ind.sma(close, 20)),
            "sma50": ind.last(ind.sma(close, 50)),
            "sma200": ind.last(ind.sma(close, 200)),
            "rsi14": ind.last(ind.rsi(close, 14)),
            "macd": ind.last(m["macd"]),
            "macd_signal": ind.last(m["signal"]),
            "macd_hist": ind.last(m["hist"]),
            "atr14": atr14,
            "atr_pct": None if atr14 is None else atr14 / price,
            "volume_ratio": volume_ratio,
            "ret_1m": ind.pct_change_over(close, 21),
            "ret_3m": ind.pct_change_over(close, 63),
            "ret_1y": ind.pct_change_over(close, 252),
            "dist_high_52w": price / high_52w - 1,
            "support": levels["support"],
            "resistance": levels["resistance"],
        }
        meta = {
            "sma20": ("Media móvil simple 20", None, {"ventana": 20}, "Media aritmética de los últimos 20 cierres."),
            "sma50": ("Media móvil simple 50", None, {"ventana": 50}, "Media aritmética de los últimos 50 cierres."),
            "sma200": ("Media móvil simple 200", None, {"ventana": 200}, "Media aritmética de los últimos 200 cierres."),
            "rsi14": ("RSI 14", None, {"periodo": 14}, "Índice de fuerza relativa de Wilder: compara subidas y bajadas medias (0-100)."),
            "macd": ("MACD", None, {"rápida": 12, "lenta": 26}, "EMA(12) − EMA(26) del cierre."),
            "macd_signal": ("Señal MACD", None, {"periodo": 9}, "EMA(9) de la línea MACD."),
            "macd_hist": ("Histograma MACD", None, {}, "MACD − señal. Positivo: el momentum de corto plazo supera al de medio."),
            "atr14": ("ATR 14", None, {"periodo": 14}, "Rango verdadero medio: cuánto se mueve el precio en una sesión típica."),
            "atr_pct": ("ATR 14 / precio", "%", {}, "ATR expresado como porcentaje del último cierre."),
            "volume_ratio": ("Volumen 20s / 60s", "x", {}, "Volumen medio de 20 sesiones dividido entre el de 60."),
            "ret_1m": ("Rentabilidad 1 mes", "%", {"sesiones": 21}, "Variación del cierre en las últimas 21 sesiones."),
            "ret_3m": ("Rentabilidad 3 meses", "%", {"sesiones": 63}, "Variación del cierre en las últimas 63 sesiones."),
            "ret_1y": ("Rentabilidad 1 año", "%", {"sesiones": 252}, "Variación del cierre en las últimas 252 sesiones."),
            "dist_high_52w": ("Distancia al máximo 52s", "%", {}, "Último cierre respecto al máximo de 52 semanas."),
            "support": ("Soporte cercano", None, {"ventana": 120}, "Mínimo local agrupado más próximo por debajo del precio (método simplificado)."),
            "resistance": ("Resistencia cercana", None, {"ventana": 120}, "Máximo local agrupado más próximo por encima del precio (método simplificado)."),
        }
        indicators = [
            IndicatorValue(id=k, name=meta[k][0], value=_round(v), unit=meta[k][1], params=meta[k][2], method=meta[k][3])
            for k, v in values.items()
        ]
        interpretations = self._interpret(price, values)
        return TechnicalResult(data=data, indicators=indicators, interpretations=interpretations)

    # ---------------------------------------------------------------- reglas

    def _interpret(self, price: float, v: dict) -> list[Interpretation]:
        out: list[Interpretation] = []
        add = out.append

        for key, horizon in (("sma50", "medio plazo"), ("sma200", "largo plazo")):
            if v[key] is not None:
                above = price > v[key]
                add(Interpretation(
                    id=f"trend_price_{key}",
                    area="tendencia",
                    statement=(
                        f"El precio está {'por encima' if above else 'por debajo'} de la media de "
                        f"{key[3:]} sesiones ({pct(price / v[key] - 1)}): tendencia de {horizon} "
                        f"{'alcista' if above else 'bajista'}."
                    ),
                    stance=Stance.BULLISH if above else Stance.BEARISH,
                    rule=f"Precio > SMA{key[3:]} → alcista; precio < SMA{key[3:]} → bajista.",
                    evidence=["last_close", key],
                    caveat="Las medias móviles van con retraso: confirman tendencias, no las anticipan.",
                ))

        if v["sma50"] is not None and v["sma200"] is not None:
            golden = v["sma50"] > v["sma200"]
            add(Interpretation(
                id="trend_sma50_sma200",
                area="tendencia",
                statement=(
                    "La media de 50 sesiones está "
                    f"{'por encima' if golden else 'por debajo'} de la de 200: estructura de tendencia "
                    f"{'alcista' if golden else 'bajista'}."
                ),
                stance=Stance.BULLISH if golden else Stance.BEARISH,
                rule="SMA50 > SMA200 → estructura alcista; SMA50 < SMA200 → bajista.",
                evidence=["sma50", "sma200"],
                caveat="En mercados laterales las medias se cruzan a menudo y generan señales falsas.",
            ))

        r = v["rsi14"]
        if r is not None:
            if r >= 70:
                stance, text = Stance.NEUTRAL, "momentum muy fuerte, pero en zona de sobrecompra: posible sobreextensión"
            elif r >= 55:
                stance, text = Stance.BULLISH, "momentum positivo"
            elif r > 45:
                stance, text = Stance.NEUTRAL, "momentum neutro"
            elif r > 30:
                stance, text = Stance.BEARISH, "momentum negativo"
            else:
                stance, text = Stance.NEUTRAL, "momentum muy débil, en zona de sobreventa: posible rebote o caída persistente"
            add(Interpretation(
                id="momentum_rsi",
                area="momentum",
                statement=f"RSI(14) = {r:.1f}: {text}.",
                stance=stance,
                rule="RSI ≥ 70 sobrecompra · 55–70 positivo · 45–55 neutro · 30–45 negativo · ≤ 30 sobreventa.",
                evidence=["rsi14"],
                caveat="En tendencias fuertes el RSI puede permanecer en sobrecompra o sobreventa mucho tiempo.",
            ))

        if v["macd_hist"] is not None:
            up = v["macd_hist"] > 0
            add(Interpretation(
                id="momentum_macd",
                area="momentum",
                statement=(
                    f"El MACD está {'por encima' if up else 'por debajo'} de su señal: el impulso de "
                    f"corto plazo {'mejora' if up else 'empeora'}."
                ),
                stance=Stance.BULLISH if up else Stance.BEARISH,
                rule="Histograma MACD > 0 → impulso alcista; < 0 → impulso bajista.",
                evidence=["macd", "macd_signal", "macd_hist"],
                caveat="El MACD cambia de signo con frecuencia en rangos laterales.",
            ))

        r3 = v["ret_3m"]
        if r3 is not None:
            stance = Stance.BULLISH if r3 > 0.05 else Stance.BEARISH if r3 < -0.05 else Stance.NEUTRAL
            add(Interpretation(
                id="momentum_3m",
                area="momentum",
                statement=f"En los últimos 3 meses el precio ha variado {pct(r3)}.",
                stance=stance,
                rule="Rentabilidad 3 meses > +5% → alcista; < −5% → bajista; entre ambos → neutral.",
                evidence=["ret_3m"],
                caveat="La rentabilidad pasada no garantiza rentabilidades futuras.",
            ))

        vr, r1 = v["volume_ratio"], v["ret_1m"]
        if vr is not None and r1 is not None:
            if vr > 1.2:
                stance = Stance.BULLISH if r1 > 0 else Stance.BEARISH
                text = (
                    f"El volumen reciente es {vr:.2f} veces el habitual y acompaña a un movimiento "
                    f"{'alcista' if r1 > 0 else 'bajista'} del último mes ({pct(r1)})."
                )
            elif vr < 0.8:
                stance, text = Stance.NEUTRAL, f"El volumen reciente es bajo ({vr:.2f} veces el habitual): poco interés o convicción."
            else:
                stance, text = Stance.NEUTRAL, f"Volumen en niveles habituales ({vr:.2f} veces la media de 60 sesiones)."
            add(Interpretation(
                id="volume_confirmation",
                area="volumen",
                statement=text,
                stance=stance,
                rule="Volumen 20s/60s > 1,2 confirma la dirección del último mes; < 0,8 indica poco interés.",
                evidence=["volume_ratio", "ret_1m"],
                caveat="El volumen de un día puntual (resultados, índices) puede distorsionar la media.",
            ))

        sup, res = v["support"], v["resistance"]
        if sup is not None or res is not None:
            parts = []
            if sup is not None:
                parts.append(f"soporte aproximado en {sup:.2f} ({pct(sup / price - 1)})")
            if res is not None:
                parts.append(f"resistencia aproximada en {res:.2f} ({pct(res / price - 1)})")
            add(Interpretation(
                id="levels",
                area="soportes y resistencias",
                statement="Niveles cercanos: " + " y ".join(parts) + ".",
                stance=Stance.NEUTRAL,
                rule="Máximos/mínimos locales de las últimas 120 sesiones, agrupados si distan < 1,5%.",
                evidence=["support", "resistance", "last_close"],
                caveat="Método simplificado: son zonas orientativas, no niveles exactos.",
            ))
        return out
