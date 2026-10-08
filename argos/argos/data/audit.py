"""Auditoría de los CSV convertidos (y de sus originales de Tiingo), SIN ejecutar ninguna estrategia.

Uso:
    python -m argos.data.audit                      # activos principales de EXP-001
    python -m argos.data.audit SPY KO               # solo esos
    python -m argos.data.audit --salida informe.md  # además guarda el informe en Markdown

Para cada activo informa de: ruta, SHA-256, filas y rango; duplicados y desorden;
valores ausentes o inválidos; coherencia OHLC; huecos de calendario (distinguiendo
fines de semana y festivos de la NYSE de las sesiones que faltan de verdad);
precios repetidos; saltos extremos; procedencia; y ajustes corporativos.

Cada comprobación indica su RESULTADO y su LIMITACIÓN. Nada se corrige ni se rellena.
Código de salida: 0 sin fallos; 1 si alguna comprobación falla; 2 si falta algún fichero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from argos.data.calendar_us import non_session_reason, sessions

OK, WARN, FAIL, NA = "ok", "aviso", "fallo", "no comprobable"
EXPECTED_HEADER = ["date", "open", "high", "low", "close", "volume"]
#: Tolerancia OHLC: el ajuste multiplica por un factor y redondea, puede dejar diferencias de ~1e-6.
OHLC_TOL = 1e-6
JUMP_WARN = 0.20
STALE_RUN = 5
#: Tolerancia relativa al comparar el cambio del factor de ajuste con el evento declarado.
FACTOR_TOL = 1e-3
SPLIT_RATIOS = [1.5, 2, 3, 4, 5, 7, 8, 10, 15, 20]


@dataclass
class Check:
    id: str
    label: str
    status: str
    detail: str
    limitation: str = ""
    examples: list[str] = field(default_factory=list)


@dataclass
class AssetAudit:
    ticker: str
    csv_path: Path
    checks: list[Check] = field(default_factory=list)
    sha256: str | None = None
    rows: int = 0
    first: date | None = None
    last: date | None = None

    @property
    def status(self) -> str:
        st = {c.status for c in self.checks}
        return FAIL if FAIL in st else WARN if WARN in st or NA in st else OK


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_float(text: str) -> float | None:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ------------------------------------------------------------------ CSV convertido


def audit_csv(ticker: str, csv_path: Path, period: tuple[date, date] | None = None) -> AssetAudit:
    a = AssetAudit(ticker=ticker, csv_path=csv_path)
    add = a.checks.append
    if not csv_path.is_file():
        add(Check("fichero", "Fichero presente", FAIL, f"No existe {csv_path}."))
        return a
    a.sha256 = _sha(csv_path)
    raw_bytes = csv_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        add(Check("codificacion", "Texto UTF-8", FAIL, "El fichero no es UTF-8."))
        return a
    lines = text.splitlines()
    header = [h.strip() for h in (lines[0].split(",") if lines else [])]
    add(Check("cabecera", "Cabecera exacta", OK if header == EXPECTED_HEADER else FAIL,
              f"Cabecera: {','.join(header)}", "Se espera exactamente date,open,high,low,close,volume."))

    dates: list[date] = []
    bad_values: list[str] = []
    rows: list[tuple[date, float, float, float, float, float]] = []
    for n, row in enumerate(csv.reader(lines[1:]), start=2):
        if len(row) != 6:
            bad_values.append(f"línea {n}: {len(row)} campos")
            continue
        try:
            d = date.fromisoformat(row[0].strip())
        except ValueError:
            bad_values.append(f"línea {n}: fecha {row[0]!r}")
            continue
        vals = [_parse_float(x) for x in row[1:]]
        if any(v is None for v in vals):
            bad_values.append(f"línea {n} ({d}): valor vacío o no numérico")
            continue
        o, h, l, c, v = vals  # noqa: E741
        if min(o, h, l, c) <= 0 or v < 0:
            bad_values.append(f"línea {n} ({d}): precio ≤ 0 o volumen negativo")
            continue
        dates.append(d)
        rows.append((d, o, h, l, c, v))
    a.rows = len(rows)
    add(Check("valores", "Sin valores ausentes ni inválidos", FAIL if bad_values else OK,
              f"{len(bad_values)} fila(s) con problemas." if bad_values else f"{len(rows)} filas válidas.",
              "Comprueba formato y signo; no puede saber si un valor plausible es correcto.", bad_values[:8]))
    if not rows:
        return a
    a.first, a.last = min(dates), max(dates)

    dup = [str(d) for d, k in Counter(dates).items() if k > 1]
    unsorted = sum(1 for x, y in zip(dates, dates[1:]) if y < x)
    add(Check("orden", "Sin fechas duplicadas ni desordenadas", FAIL if dup or unsorted else OK,
              f"{len(dup)} duplicada(s), {unsorted} inversión(es) de orden.", "", dup[:8]))

    rows_sorted = sorted(set(rows), key=lambda r: r[0])
    incoherent = [str(d) for d, o, h, l, c, _ in rows_sorted
                  if h < max(o, c) * (1 - OHLC_TOL) or l > min(o, c) * (1 + OHLC_TOL) or l > h * (1 + OHLC_TOL)]
    add(Check("ohlc", "Coherencia OHLC", WARN if incoherent else OK,
              f"{len(incoherent)} sesión(es) incoherentes." if incoherent else "mínimo ≤ apertura, cierre ≤ máximo en todas.",
              f"Tolerancia relativa {OHLC_TOL:g} por el redondeo del ajuste.", incoherent[:8]))

    # Calendario NYSE
    got = set(dates)
    lo, hi = (period if period else (a.first, a.last))
    expected = set(sessions(max(lo, a.first) if not period else lo, hi))
    missing = sorted(expected - got)
    # Cualquier fecha que no fue sesión (fin de semana, festivo, cierre) es un error, esté donde esté.
    extra = sorted(d for d in got if non_session_reason(d))
    outside = sorted(d for d in got if not (lo <= d <= hi) and not non_session_reason(d))
    extra_txt = [f"{d} ({non_session_reason(d)})" for d in extra] + [f"{d} (fuera del periodo)" for d in outside]
    extra = extra + outside
    status = FAIL if missing or extra else OK
    add(Check("calendario", "Sesiones según el calendario NYSE", status,
              f"Esperadas {len(expected)} entre {lo} y {hi}; faltan {len(missing)}; sobran {len(extra)} "
              "(fechas sin sesión: fin de semana o festivo).",
              "Calendario de la NYSE (festivos y cierres extraordinarios 2000-2030), validado contra "
              "pandas_market_calendars en 2000-2025. Activos que no cotizan en la NYSE requieren otro calendario.",
              [f"falta {d}" for d in missing[:6]] + [f"sobra {x}" for x in extra_txt[:6]]))

    stale, run = [], 1
    for prev, cur in zip(rows_sorted, rows_sorted[1:]):
        run = run + 1 if prev[1:5] == cur[1:5] else 1
        if run == STALE_RUN:
            stale.append(str(cur[0]))
    add(Check("repetidos", "Sin precios repetidos sospechosos", WARN if stale else OK,
              f"{len(stale)} tramo(s) de {STALE_RUN}+ sesiones con OHLC idéntico." if stale else "Ninguno.",
              "Un tramo repetido suele indicar relleno de datos, pero puede ser real en activos muy ilíquidos.", stale[:8]))

    jumps, split_like = [], []
    for prev, cur in zip(rows_sorted, rows_sorted[1:]):
        c0, c1 = prev[4], cur[4]
        mv = c1 / c0 - 1
        if abs(mv) > JUMP_WARN:
            label = f"{prev[0]} → {cur[0]}: {mv:+.1%}"
            jumps.append(label)
            if any(abs((c0 / c1) / r - 1) < 0.03 or abs((c1 / c0) / r - 1) < 0.03 for r in SPLIT_RATIOS):
                split_like.append(label)
    add(Check("saltos", f"Saltos diarios > {JUMP_WARN:.0%}", FAIL if split_like else WARN if jumps else OK,
              (f"{len(jumps)} salto(s); {len(split_like)} con proporción de split." if jumps else "Ninguno."),
              "En una serie AJUSTADA los splits no deben producir saltos: un salto con forma de split indica "
              "un ajuste que falta. Su ausencia NO demuestra que no hubiera splits (ver ajustes corporativos).",
              jumps[:8]))
    return a


# ------------------------------------------------------------------ procedencia y originales


def _source_fields(text: str) -> dict:
    shas = re.findall(r"SHA-256 ([0-9a-f]{64})", text)
    tick = re.search(r"^Ticker: (\S+)", text, re.M)
    raw = re.search(r"data/raw/tiingo/(\S+\.csv)", text)
    return {"raw_sha": shas[0] if shas else None, "csv_sha": shas[1] if len(shas) > 1 else None,
            "ticker": tick.group(1) if tick else None, "raw_file": raw.group(1) if raw else None}


def audit_provenance(a: AssetAudit, raw_dir: Path) -> None:
    from argos.data.sources import tiingo

    add = a.checks.append
    src = a.csv_path.with_suffix(".source.txt")
    if not src.is_file():
        add(Check("procedencia", "Metadatos de procedencia", FAIL, f"Falta {src.name}.",
                  "Sin procedencia no se puede reproducir ni atribuir el dato."))
        return
    meta = _source_fields(src.read_text(encoding="utf-8"))
    problems = []
    if meta["ticker"] and meta["ticker"] != a.ticker:
        problems.append(f"el .source.txt es de {meta['ticker']}, no de {a.ticker} (¿símbolo cambiado o fichero copiado?)")
    if meta["csv_sha"] and a.sha256 and meta["csv_sha"] != a.sha256:
        problems.append("el CSV ha cambiado desde la conversión (SHA-256 distinto del registrado)")
    if not meta["csv_sha"]:
        problems.append("el .source.txt no registra la huella del CSV")
    add(Check("procedencia", "Metadatos de procedencia coherentes", FAIL if problems else OK,
              "; ".join(problems) if problems else f"{src.name} coincide con el ticker y la huella del CSV.",
              "Comprueba coherencia interna; el origen declarado no se puede verificar desde aquí."))

    entries = [e for e in tiingo.read_manifest(raw_dir) if e.get("ticker") == a.ticker and e.get("status") == "ok"]
    if not entries:
        add(Check("original", "Original de Tiingo disponible", NA, f"No hay descargas de {a.ticker} en {raw_dir}.",
                  "Sin el original no se pueden auditar los ajustes corporativos."))
        return
    entry = next((e for e in reversed(entries) if e["raw_file"] == meta["raw_file"]), entries[-1])
    raw_path = raw_dir / entry["raw_file"]
    if not raw_path.is_file():
        add(Check("original", "Original de Tiingo disponible", FAIL, f"Falta {raw_path.name}."))
        return
    raw_sha = _sha(raw_path)
    intact = raw_sha == entry["sha256"] and (meta["raw_sha"] in (None, raw_sha))
    add(Check("original", "Original intacto (SHA-256)", OK if intact else FAIL,
              f"{raw_path.name} · SHA-256 {raw_sha[:16]}… " + ("coincide con el manifiesto." if intact else "NO coincide."),
              "Detecta cualquier modificación posterior a la descarga."))
    if not intact:
        return
    try:
        series = tiingo.parse_raw(raw_path.read_text(encoding="utf-8"), raw_path.name,
                                  date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"]))
    except tiingo.TiingoError as exc:
        add(Check("original_formato", "Original legible", FAIL, str(exc)))
        return
    same = tiingo.render_converted(series) == a.csv_path.read_bytes()
    add(Check("conversion", "Conversión reproducible", OK if same else FAIL,
              "Rehacer la conversión desde el original da exactamente los mismos bytes." if same
              else "El CSV NO coincide con la conversión del original.",
              "Garantiza que el CSV es mecánicamente el original; no valida al proveedor."))
    audit_corporate_actions(a, series)


def audit_corporate_actions(a: AssetAudit, series) -> None:
    """Coherencia entre los eventos que declara Tiingo y sus propios precios ajustados.

    factor_t = adjClose_t / close_t. Con ajuste hacia atrás (tipo CRSP), entre dos sesiones
    consecutivas debe cumplirse:  factor_{t-1} / factor_t ≈ (1 − divCash_t / close_{t-1}) / splitFactor_t.
    En días sin evento la razón es 1. Así se detectan: cambios de factor sin evento declarado,
    eventos declarados sin ajuste, y magnitudes que no cuadran.
    """
    add = a.checks.append
    rows = series.rows
    splits = [(r.date, r.values["splitFactor"]) for r in rows if float(r.values["splitFactor"]) != 1]
    divs = Counter(r.date.year for r in rows if float(r.values["divCash"]) > 0)
    years = range(rows[0].date.year, rows[-1].date.year + 1)
    add(Check("eventos", "Eventos corporativos declarados por Tiingo (pendiente de verificación externa)", NA,
              f"Splits (splitFactor ≠ 1): {', '.join(f'{d} ×{f}' for d, f in splits) or 'ninguno'}. "
              f"Dividendos por año: {', '.join(f'{y}:{divs.get(y, 0)}' for y in years)}.",
              "Es lo que DECLARA el proveedor. Debe contrastarse con fuentes oficiales (relación con inversores, "
              "folleto del ETF): esta herramienta no lo hace."))

    no_event, unmatched = [], []
    for prev, cur in zip(rows, rows[1:]):
        f_prev = float(prev.values["adjClose"]) / float(prev.values["close"])
        f_cur = float(cur.values["adjClose"]) / float(cur.values["close"])
        observed = f_prev / f_cur
        div = float(cur.values["divCash"])
        sf = float(cur.values["splitFactor"])
        expected = (1 - div / float(prev.values["close"])) / sf
        if abs(observed / expected - 1) > FACTOR_TOL:
            if div > 0 or sf != 1:
                unmatched.append(f"{cur.date}: razón {observed:.6f}, esperada {expected:.6f} (div {div}, split {sf})")
            else:
                no_event.append(f"{cur.date}: el factor cambia ({observed:.6f}) sin evento declarado")
    add(Check("ajustes", "Ajustes coherentes con los eventos", FAIL if (no_event or unmatched) else OK,
              f"{len(no_event)} cambio(s) de factor sin evento; {len(unmatched)} evento(s) sin el ajuste "
              f"correspondiente o con magnitud distinta. Tolerancia relativa {FACTOR_TOL:g}.",
              "Supone el método de ajuste multiplicativo hacia atrás (tipo CRSP), que Tiingo no documenta "
              "públicamente con detalle. Un fallo aquí puede indicar otro método, no necesariamente un error. "
              "No detecta un evento que falte a la vez en divCash/splitFactor y en el ajuste.",
              (no_event + unmatched)[:8]))

    raw_jumps = []
    for prev, cur in zip(rows, rows[1:]):
        r = float(prev.values["close"]) / float(cur.values["close"])
        for s in SPLIT_RATIOS:
            for target in (s, 1 / s):
                if abs(r / target - 1) < 0.03 and float(cur.values["splitFactor"]) == 1:
                    raw_jumps.append(f"{prev.date} → {cur.date}: cierre sin ajustar ×{1 / r:.3f}")
    add(Check("splits_no_declarados", "Sin saltos con forma de split no declarados", WARN if raw_jumps else OK,
              f"{len(raw_jumps)} salto(s) en el precio SIN ajustar con proporción de split y splitFactor = 1."
              if raw_jumps else "Ningún salto del precio sin ajustar con forma de split fuera de los declarados.",
              "Busca splits que el proveedor no declara. Un movimiento real grande podría parecerse a una proporción.",
              raw_jumps[:8]))


# ------------------------------------------------------------------ informe


def render(audits: list[AssetAudit]) -> str:
    icon = {OK: "✅", WARN: "⚠️", FAIL: "⛔", NA: "❔"}
    out = ["# Auditoría de datos de ARGOS", "",
           "Sin ejecutar ninguna estrategia. Cada comprobación indica su resultado y su limitación.", ""]
    for a in audits:
        out += [f"## {a.ticker} — {icon[a.status]} {a.status.upper()}", "",
                f"- Fichero: `{a.csv_path}`",
                f"- SHA-256: `{a.sha256 or 'n/d'}`",
                f"- Filas: {a.rows} · rango: {a.first} → {a.last}", "",
                "| Comprobación | Resultado | Detalle | Limitación |", "| --- | --- | --- | --- |"]
        for c in a.checks:
            ex = f" Ejemplos: {'; '.join(c.examples)}." if c.examples else ""
            out.append(f"| {c.label} | {icon[c.status]} {c.status} | {c.detail}{ex} | {c.limitation} |")
        out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    from argos.data.sources import tiingo
    from argos.experiments.protocol import load_protocol

    ap = argparse.ArgumentParser(description="Audita los CSV de ARGOS sin ejecutar ninguna estrategia.")
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--protocolo", default="EXP-001")
    ap.add_argument("--csv-dir", type=Path, default=tiingo.CSV_DIR)
    ap.add_argument("--raw-dir", type=Path, default=tiingo.RAW_DIR)
    ap.add_argument("--salida", type=Path, default=None, help="Guardar también el informe en Markdown.")
    args = ap.parse_args(argv)

    protocol, _, _ = load_protocol(args.protocolo)
    tickers = [t.upper() for t in args.tickers] or [x.ticker for x in protocol.assets if x.core]
    req = protocol.data_requirements
    # Rango de sesiones esperadas: desde la primera sesión del año requerido hasta el final requerido.
    start = sessions(date.fromisoformat(req["required_start"]), date.fromisoformat(req["required_end"]))[0]
    period = (start, date.fromisoformat(req["required_end"]))

    audits = []
    for t in tickers:
        a = audit_csv(t, args.csv_dir / f"{t}.csv", period)
        if a.rows:
            audit_provenance(a, args.raw_dir)
        audits.append(a)
    report = render(audits)
    print(report)
    if args.salida:
        args.salida.write_text(report, encoding="utf-8")
        print(f"Informe guardado en {args.salida}")
    if any(not a.csv_path.is_file() for a in audits):
        return 2
    return 1 if any(a.status == FAIL for a in audits) else 0


if __name__ == "__main__":
    sys.exit(main())
