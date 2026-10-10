"""Calendario de sesiones de la bolsa de Nueva York (NYSE), para auditar huecos.

Sirve para distinguir los días sin datos que son NORMALES (fines de semana,
festivos, cierres extraordinarios) de los HUECOS reales (sesiones que existieron
y faltan en el fichero). No se usa para rellenar nada.

Reglas (vigentes en 2000-2030):
  - Año Nuevo, Juneteenth (desde 2022), Independencia y Navidad: si caen en
    sábado se cierra el viernes anterior; si caen en domingo, el lunes siguiente.
    Excepción: si el 1 de enero es sábado, NO se cierra el viernes 31 de diciembre.
  - Martin Luther King (3.er lunes de enero), Presidentes (3.er lunes de febrero),
    Viernes Santo, Memorial Day (último lunes de mayo), Trabajo (1.er lunes de
    septiembre), Acción de Gracias (4.º jueves de noviembre).
  - Cierres extraordinarios de la lista CLOSURES.

El calendario se validó contra la librería independiente `pandas_market_calendars`
para 2000-2025 (ver docs/AUDITORIA_EXP-001.md). No incluye medias sesiones: los
días de cierre anticipado son sesiones normales a efectos de datos diarios.
"""

from __future__ import annotations

from datetime import date, timedelta

#: Cierres extraordinarios de la NYSE (días laborables sin sesión).
CLOSURES: dict[date, str] = {
    date(2001, 9, 11): "atentados del 11-S",
    date(2001, 9, 12): "atentados del 11-S",
    date(2001, 9, 13): "atentados del 11-S",
    date(2001, 9, 14): "atentados del 11-S",
    date(2004, 6, 11): "funeral de Estado de Ronald Reagan",
    date(2007, 1, 2): "luto nacional por Gerald Ford",
    date(2012, 10, 29): "huracán Sandy",
    date(2012, 10, 30): "huracán Sandy",
    date(2018, 12, 5): "luto nacional por George H. W. Bush",
    date(2025, 1, 9): "luto nacional por Jimmy Carter",
}


def _easter(year: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo de Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date | None:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def holidays(year: int) -> dict[date, str]:
    out: dict[date, str] = {}
    ny = date(year, 1, 1)
    if ny.weekday() != 5:  # 1 de enero en sábado: no se cierra el 31 de diciembre anterior
        out[_observed(ny)] = "Año Nuevo"
    out[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King"
    out[_nth_weekday(year, 2, 0, 3)] = "Presidentes"
    out[_easter(year) - timedelta(days=2)] = "Viernes Santo"
    out[_last_weekday(year, 5, 0)] = "Memorial Day"
    if year >= 2022:
        out[_observed(date(year, 6, 19))] = "Juneteenth"
    out[_observed(date(year, 7, 4))] = "Independencia"
    out[_nth_weekday(year, 9, 0, 1)] = "Día del Trabajo"
    out[_nth_weekday(year, 11, 3, 4)] = "Acción de Gracias"
    out[_observed(date(year, 12, 25))] = "Navidad"
    for d, why in CLOSURES.items():
        if d.year == year:
            out[d] = why
    return out


def non_session_reason(d: date) -> str | None:
    """Por qué `d` no es sesión de la NYSE, o None si sí lo es."""
    if d.weekday() >= 5:
        return "fin de semana"
    return holidays(d.year).get(d)


def sessions(start: date, end: date) -> list[date]:
    """Sesiones esperadas de la NYSE entre start y end (ambos incluidos)."""
    hol: dict[date, str] = {}
    for y in range(start.year, end.year + 1):
        hol.update(holidays(y))
    out, d = [], start
    while d <= end:
        if d.weekday() < 5 and d not in hol:
            out.append(d)
        d += timedelta(days=1)
    return out
