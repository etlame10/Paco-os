"""Control de integridad de un histórico, ANTES de usarlo.

Se ejecuta sobre los datos en bruto (antes de normalizar) para que ningún
problema quede oculto. Cada comprobación devuelve:
    ok        → superada
    aviso     → algo sospechoso; se puede continuar, pero se muestra siempre
    bloqueo   → los datos no son aptos (p. ej. un split sin ajustar falsearía el backtest)

ARGOS nunca corrige datos: solo informa.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from pydantic import BaseModel, Field

from argos.core.models import Bar, PriceHistory

OK, WARN, FAIL = "ok", "aviso", "bloqueo"

#: Días naturales entre sesiones consecutivas a partir de los que se avisa / se bloquea.
GAP_WARN_DAYS = 7  # p. ej. el cierre tras el 11-S duró 6 días hábiles (7 naturales)
GAP_FAIL_DAYS = 20
#: Sesiones mínimas esperadas en un año natural completo (bolsa: ~252).
MIN_BARS_PER_FULL_YEAR = 240
#: Variación diaria del cierre a partir de la cual se investiga.
JUMP_THRESHOLD = 0.40
#: Proporciones típicas de split (y contrasplit).
SPLIT_RATIOS = [1.5, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 30, 50]
SPLIT_TOLERANCE = 0.03
STALE_RUN = 5
MAX_INTRADAY_RANGE = 0.5


class QualityRequirements(BaseModel):
    required_start: date | None = None
    required_end: date | None = None
    max_start_tolerance_days: int = 10
    min_years: float | None = None
    min_bars: int | None = None


class QualityCheck(BaseModel):
    id: str
    label: str
    status: str
    detail: str
    examples: list[str] = Field(default_factory=list)


class DataQualityReport(BaseModel):
    ticker: str
    status: str  # "superado" | "con avisos" | "bloqueado"
    first_date: date | None
    last_date: date | None
    n_bars: int
    checks: list[QualityCheck]

    @property
    def blocked(self) -> bool:
        return self.status == "bloqueado"

    def summary(self) -> str:
        c = Counter(ch.status for ch in self.checks)
        return f"{self.status}: {c[OK]} ok, {c[WARN]} aviso(s), {c[FAIL]} bloqueo(s)"


def _split_ratio(prev: float, cur: float) -> float | None:
    """Si el salto prev→cur se parece a un split n:1 (o contrasplit), devuelve n."""
    r = prev / cur
    for n in SPLIT_RATIOS:
        for target in (n, 1 / n):
            if abs(r / target - 1) <= SPLIT_TOLERANCE:
                return target
    return None


def assess_quality(history: PriceHistory, requirements: QualityRequirements | None = None) -> DataQualityReport:
    bars: list[Bar] = sorted(history.bars, key=lambda b: b.date)
    checks: list[QualityCheck] = []

    def add(id_: str, label: str, status: str, detail: str, examples: list[str] | None = None) -> None:
        checks.append(QualityCheck(id=id_, label=label, status=status, detail=detail, examples=examples or []))

    if not bars:
        add("datos", "Hay datos", FAIL, "El histórico está vacío.")
        return DataQualityReport(ticker=history.ticker, status="bloqueado", first_date=None, last_date=None,
                                 n_bars=0, checks=checks)
    first, last = bars[0].date, bars[-1].date
    dates = [b.date for b in bars]

    # 1) Fechas
    future = [d for d in dates if d > date.today()]
    add("fechas", "Fechas válidas", FAIL if future else OK,
        f"{len(future)} fecha(s) en el futuro." if future else f"Del {first} al {last}, ordenables y sin fechas futuras.",
        [str(d) for d in future[:5]])

    # 2) Duplicados
    dup = [d for d, n in Counter(dates).items() if n > 1]
    add("duplicados", "Sin fechas duplicadas", FAIL if dup else OK,
        f"{len(dup)} fecha(s) repetida(s)." if dup else "Una sola fila por sesión.", [str(d) for d in dup[:5]])

    # 3) Frecuencia y huecos
    gaps = [(a, b, (b - a).days) for a, b in zip(dates, dates[1:])]
    gap_days = sorted(g[2] for g in gaps)
    median_gap = gap_days[len(gap_days) // 2] if gap_days else 0
    add("frecuencia", "Frecuencia diaria", OK if median_gap <= 4 else FAIL,
        f"Separación típica entre filas: {median_gap} día(s)." + ("" if median_gap <= 4 else " No parece diaria."))
    big = [g for g in gaps if g[2] > GAP_WARN_DAYS]
    huge = [g for g in gaps if g[2] > GAP_FAIL_DAYS]
    add("huecos", "Sin huecos importantes", FAIL if huge else WARN if big else OK,
        (f"{len(big)} hueco(s) de más de {GAP_WARN_DAYS} días naturales"
         + (f", {len(huge)} de más de {GAP_FAIL_DAYS}" if huge else "") + ". Pueden faltar datos."
         if big else f"Ningún hueco de más de {GAP_WARN_DAYS} días naturales."),
        [f"{a} → {b} ({d} días)" for a, b, d in big[:5]])

    per_year = Counter(d.year for d in dates)
    full_years = [y for y in per_year if first.year < y < last.year]
    thin = [y for y in full_years if per_year[y] < MIN_BARS_PER_FULL_YEAR]
    add("sesiones_por_anio", "Sesiones suficientes por año", WARN if thin else OK,
        (f"{len(thin)} año(s) completo(s) con menos de {MIN_BARS_PER_FULL_YEAR} sesiones." if thin
         else f"Todos los años completos tienen al menos {MIN_BARS_PER_FULL_YEAR} sesiones."),
        [f"{y}: {per_year[y]} sesiones" for y in thin[:5]])

    # 4) Valores imposibles
    nonpos = [b.date for b in bars if min(b.open, b.high, b.low, b.close) <= 0]
    add("precios_positivos", "Precios positivos", FAIL if nonpos else OK,
        f"{len(nonpos)} sesión(es) con precios ≤ 0." if nonpos else "Todos los precios son positivos.",
        [str(d) for d in nonpos[:5]])

    # 5) Coherencia OHLC
    bad = [b.date for b in bars
           if b.high < max(b.open, b.close) or b.low > min(b.open, b.close) or b.low > b.high]
    share = len(bad) / len(bars)
    add("ohlc", "Coherencia apertura/máximo/mínimo/cierre", FAIL if share > 0.01 else WARN if bad else OK,
        (f"{len(bad)} sesión(es) ({share:.2%}) donde el máximo/mínimo no contiene a la apertura y el cierre. "
         "Se descartarán al normalizar." if bad else "En todas las sesiones mínimo ≤ apertura, cierre ≤ máximo."),
        [str(d) for d in bad[:5]])
    wide = [b.date for b in bars if b.low > 0 and b.high / b.low - 1 > MAX_INTRADAY_RANGE]
    add("rango_diario", "Rangos diarios plausibles", WARN if wide else OK,
        (f"{len(wide)} sesión(es) con un rango máximo/mínimo superior al {MAX_INTRADAY_RANGE:.0%}." if wide
         else f"Ninguna sesión con un rango superior al {MAX_INTRADAY_RANGE:.0%}."),
        [str(d) for d in wide[:5]])

    # 6) Volumen
    negv = [b.date for b in bars if b.volume < 0]
    zero = [b.date for b in bars if b.volume == 0]
    if negv:
        add("volumen", "Volumen válido", FAIL, f"{len(negv)} sesión(es) con volumen negativo.", [str(d) for d in negv[:5]])
    elif len(zero) == len(bars):
        add("volumen", "Volumen válido", WARN, "El fichero no tiene volumen (todo 0). El backtest no lo usa, pero el análisis de volumen no será fiable.")
    elif len(zero) / len(bars) > 0.05:
        add("volumen", "Volumen válido", WARN, f"{len(zero)} sesión(es) ({len(zero)/len(bars):.1%}) con volumen 0.", [str(d) for d in zero[:5]])
    else:
        add("volumen", "Volumen válido", OK, f"Sin volúmenes negativos; {len(zero)} sesión(es) con volumen 0.")

    # 7) Precios congelados (posible relleno de datos)
    runs, run = [], 1
    for prev, cur in zip(bars, bars[1:]):
        same = (prev.open, prev.high, prev.low, prev.close) == (cur.open, cur.high, cur.low, cur.close)
        run = run + 1 if same else 1
        if run == STALE_RUN:
            runs.append(cur.date)
    add("precios_congelados", "Sin precios repetidos sospechosos", WARN if runs else OK,
        (f"{len(runs)} tramo(s) de {STALE_RUN} o más sesiones idénticas: posible relleno de datos." if runs
         else f"Ningún tramo de {STALE_RUN} sesiones idénticas."), [str(d) for d in runs[:5]])

    # 8) Splits y saltos
    splits, jumps = [], []
    for prev, cur in zip(bars, bars[1:]):
        if prev.close <= 0 or cur.close <= 0:
            continue
        move = cur.close / prev.close - 1
        if abs(move) > JUMP_THRESHOLD:
            ratio = _split_ratio(prev.close, cur.close)
            label = f"{prev.date} → {cur.date}: {move:+.0%}"
            if ratio is not None:
                n = ratio if ratio >= 1 else 1 / ratio
                splits.append(f"{label} (≈ {'split' if ratio >= 1 else 'contrasplit'} {n:g}:1)")
            else:
                jumps.append(label)
    if splits:
        add("splits", "Sin splits sin ajustar", FAIL,
            f"{len(splits)} salto(s) con la proporción típica de un split. Si los precios no están ajustados, "
            "el backtest contaría una pérdida o ganancia que no existió. Usa precios ajustados.", splits[:5])
    else:
        add("splits", "Sin splits sin ajustar", OK,
            "No se detectan saltos con proporción de split. (El ajuste por dividendos no se puede verificar: "
            "confírmalo con tu fuente.)")
    add("saltos", f"Sin saltos diarios > {JUMP_THRESHOLD:.0%}", WARN if jumps else OK,
        (f"{len(jumps)} variación(es) diaria(s) de más del {JUMP_THRESHOLD:.0%}. Pueden ser reales (crisis, "
         "resultados) o errores: revísalas." if jumps else f"Ninguna variación diaria superior al {JUMP_THRESHOLD:.0%}."),
        jumps[:5])

    # 9) Longitud y cobertura
    years = (last - first).days / 365.25
    if requirements:
        problems = []
        if requirements.required_start and (first - requirements.required_start).days > requirements.max_start_tolerance_days:
            problems.append(f"empieza el {first}, se necesita desde {requirements.required_start}")
        if requirements.required_end and last < requirements.required_end:
            problems.append(f"termina el {last}, se necesita hasta {requirements.required_end}")
        if requirements.min_years and years < requirements.min_years:
            problems.append(f"cubre {years:.1f} años, se necesitan {requirements.min_years:g}")
        if requirements.min_bars and len(bars) < requirements.min_bars:
            problems.append(f"tiene {len(bars)} sesiones, se necesitan {requirements.min_bars}")
        add("longitud", "Histórico suficiente", FAIL if problems else OK,
            ("; ".join(problems).capitalize() + ".") if problems
            else f"{len(bars)} sesiones ({years:.1f} años), cubre el periodo requerido.")
    else:
        add("longitud", "Histórico suficiente", OK if years >= 10 else WARN,
            f"{len(bars)} sesiones ({years:.1f} años)." + ("" if years >= 10 else " Menos de 10 años: resultados poco representativos."))

    statuses = {c.status for c in checks}
    status = "bloqueado" if FAIL in statuses else "con avisos" if WARN in statuses else "superado"
    return DataQualityReport(ticker=history.ticker, status=status, first_date=first, last_date=last,
                             n_bars=len(bars), checks=checks)
