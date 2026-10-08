"""Tiingo → datos originales → conversión → CSV de ARGOS.

Diseño conservador:
  - La clave se lee SOLO de la variable de entorno TIINGO_API_KEY. Se envía en
    la cabecera HTTP `Authorization` (nunca en la URL, que acaba en logs), no se
    imprime y se borra de cualquier mensaje de error.
  - Activos y fechas salen del protocolo pre-registrado (solo lectura).
  - El fichero descargado se guarda byte a byte, sin tocar, en data/raw/tiingo/,
    con nombre único (nunca se sobrescribe), y se anota en un manifiesto con la
    fecha de descarga y su SHA-256.
  - La conversión es MECÁNICA: copia literalmente el texto de las columnas
    ajustadas de Tiingo (adjOpen, adjHigh, adjLow, adjClose, adjVolume) y
    normaliza solo el formato de la fecha. No calcula, redondea, rellena ni
    interpola nada.
  - Ante cualquier respuesta inesperada, incompleta o ambigua: se detiene y
    explica por qué. Nunca intenta "arreglar" los datos.

Esta capa no ejecuta operaciones de mercado: solo descarga históricos públicos.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import certifi

from argos import __version__
from argos.experiments.registry import ARGOS_ROOT, file_sha256

API_HOST = "api.tiingo.com"
API_BASE = f"https://{API_HOST}/tiingo/daily"
ENV_KEY = "TIINGO_API_KEY"
RAW_DIR = ARGOS_ROOT / "data" / "raw" / "tiingo"
CSV_DIR = ARGOS_ROOT / "data" / "csv"
MANIFEST = "manifest.jsonl"

#: Columnas que Tiingo debe devolver. Si falta alguna, se rechaza la respuesta.
RAW_COLUMNS = ("date", "open", "high", "low", "close", "volume",
               "adjOpen", "adjHigh", "adjLow", "adjClose", "adjVolume", "divCash", "splitFactor")
#: Correspondencia mecánica columna de ARGOS ← columna ajustada de Tiingo.
MAPPING = {"open": "adjOpen", "high": "adjHigh", "low": "adjLow", "close": "adjClose", "volume": "adjVolume"}
#: Tolerancia para comprobar que las cuatro columnas de precio de una fila usan el MISMO factor de ajuste.
#: (Los precios originales vienen redondeados a céntimos; 0,5 % cubre ese redondeo en precios > 2 $.)
FACTOR_TOLERANCE = 0.005
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:T00:00:00(?:\.0+)?Z?)?$")
MAX_ERROR_SNIPPET = 200


class TiingoError(RuntimeError):
    """Error que detiene el proceso. El mensaje nunca contiene la clave."""


class MissingKeyError(TiingoError):
    pass


class TiingoAuthError(TiingoError):
    pass


class TiingoResponseError(TiingoError):
    pass


class RawDataError(TiingoError):
    pass


class TiingoTLSError(TiingoError):
    """No se pudo verificar la identidad del servidor. Nunca se reintenta sin verificación."""


# ------------------------------------------------------------------ clave


def read_api_key(environ: dict | None = None) -> str:
    env = os.environ if environ is None else environ
    key = (env.get(ENV_KEY) or "").strip()
    if not key:
        raise MissingKeyError(
            f"No se encuentra la variable de entorno {ENV_KEY}. Configúrala con tu clave de Tiingo "
            "(ver docs/DATOS_REALES.md) y vuelve a ejecutar. ARGOS no busca la clave en ningún otro sitio."
        )
    if any(c.isspace() for c in key) or len(key) < 20:
        raise MissingKeyError(f"El valor de {ENV_KEY} no tiene el aspecto de una clave de Tiingo (revisa que la copiaste completa).")
    return key


def scrub(text: str, secret: str | None) -> str:
    return text.replace(secret, "***") if secret else text


# ------------------------------------------------------------------ descarga

#: fetch(url, headers) -> (status, cabeceras, cuerpo en bytes). Inyectable para tests.
Fetcher = Callable[[str, dict], tuple[int, dict, bytes]]


def tls_context() -> ssl.SSLContext:
    """Contexto TLS con verificación COMPLETA (certificado + nombre de host) y TLS ≥ 1.2.

    Las autoridades de confianza son las del paquete `certifi` (lista de Mozilla, versión
    fijada en requirements.txt), no el almacén de Windows: Python no activa la descarga
    automática de raíces de Windows y puede acabar construyendo una cadena con un
    certificado caducado. Así la confianza es explícita, actualizable y reproducible.
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if ctx.verify_mode != ssl.CERT_REQUIRED or not ctx.check_hostname:  # salvaguarda: nunca sin verificar
        raise TiingoTLSError("Contexto TLS sin verificación: no se permite.")
    return ctx


def _tls_message(err: ssl.SSLError) -> str:
    detail = getattr(err, "verify_message", None) or getattr(err, "reason", None) or str(err)
    return (
        f"No se pudo verificar el certificado de {API_HOST} ({detail}). ARGOS no se conecta sin verificar. "
        "Causas habituales: el reloj del PC tiene mal la fecha u hora; un antivirus o proxy inspecciona "
        "las conexiones HTTPS; o el paquete de certificados está desactualizado (pip install -U -r requirements.txt). "
        "Diagnóstico sin clave y sin descargar datos: python -m argos.tools.tiingo diagnosticar-tls"
    )


def urllib_fetch(url: str, headers: dict, timeout: float = 60.0) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read() or b""
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLError):
            raise TiingoTLSError(_tls_message(exc.reason)) from None
        raise TiingoResponseError(f"No se pudo conectar con Tiingo: {exc.reason}.") from None
    except ssl.SSLError as exc:
        raise TiingoTLSError(_tls_message(exc)) from None


def diagnose_tls(host: str = API_HOST, port: int = 443, timeout: float = 15.0,
                 handshake: Callable | None = None) -> tuple[bool, list[str]]:
    """Solo abre una conexión TLS verificada y la cierra: no envía la clave ni pide datos.

    Compara la confianza de `certifi` (la que usa ARGOS) con la del sistema operativo, para
    distinguir entre reloj incorrecto, antivirus/proxy que intercepta HTTPS y certificados
    desactualizados. Nunca prueba sin verificación.
    """
    handshake = handshake or _handshake
    lines = [
        f"Fecha y hora de este PC (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}  ← compárala con la hora real",
        f"Python {sys.version.split()[0]} · {ssl.OPENSSL_VERSION}",
        f"certifi {certifi.__version__} · {certifi.where()}",
    ]
    results = {}
    for name, ctx_factory in (("certifi (la que usa ARGOS)", tls_context), ("sistema operativo", ssl.create_default_context)):
        try:
            cert = handshake(host, port, timeout, ctx_factory())
            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            results[name] = True
            lines.append(f"[OK]    Confianza {name}: certificado de {subject.get('commonName', '?')} "
                         f"emitido por {issuer.get('organizationName', issuer.get('commonName', '?'))}, "
                         f"válido hasta {cert.get('notAfter', '?')}")
        except ssl.SSLCertVerificationError as exc:
            results[name] = False
            lines.append(f"[FALLO] Confianza {name}: {exc.verify_message} (código {exc.verify_code})")
        except (ssl.SSLError, OSError) as exc:
            results[name] = False
            lines.append(f"[FALLO] Confianza {name}: {exc}")
    ok = results.get("certifi (la que usa ARGOS)", False)
    if ok:
        lines.append("Conclusión: ARGOS puede conectar con Tiingo verificando el certificado.")
    elif results.get("sistema operativo"):
        lines.append("Conclusión: solo funciona con los certificados de Windows. Suele indicar un antivirus o proxy que "
                     "intercepta HTTPS con su propio certificado. Revisa la opción de análisis HTTPS de tu antivirus.")
    else:
        lines.append("Conclusión: falla con ambos. Comprueba primero la fecha y hora del PC (Configuración → Hora e idioma → "
                     "Sincronizar ahora) y después el antivirus/proxy. No desactives la verificación.")
    return ok, lines


def _handshake(host: str, port: int, timeout: float, ctx: ssl.SSLContext) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            return tls.getpeercert()


def build_url(ticker: str, start: date, end: date) -> str:
    """URL SIN clave: la clave va en la cabecera Authorization."""
    query = urllib.parse.urlencode({
        "startDate": start.isoformat(), "endDate": end.isoformat(), "format": "csv", "resampleFreq": "daily",
    })
    return f"{API_BASE}/{ticker.lower()}/prices?{query}"


@dataclass
class DownloadRecord:
    ticker: str
    url: str
    start: str
    end: str
    downloaded_at: str
    raw_file: str
    sha256: str
    bytes: int
    rows: int
    first_date: str
    last_date: str
    http_status: int
    argos_version: str
    status: str = "ok"

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False)


def validate_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if not TICKER_RE.match(t):
        raise TiingoError(f"Ticker no válido: {ticker!r}.")
    return t


def check_response(ticker: str, status: int, body: bytes, key: str | None = None) -> None:
    """Valida la respuesta HTTP ANTES de guardar nada. Lanza TiingoError si algo no cuadra."""
    snippet = scrub(body[:MAX_ERROR_SNIPPET].decode("utf-8", errors="replace").strip(), key)
    if status in (401, 403):
        raise TiingoAuthError(
            f"{ticker}: Tiingo rechazó la autenticación (HTTP {status}). Revisa que {ENV_KEY} contiene tu clave "
            f"correcta y vigente. Respuesta: {snippet!r}"
        )
    if status == 404:
        raise TiingoResponseError(f"{ticker}: Tiingo no reconoce el ticker (HTTP 404). Respuesta: {snippet!r}")
    if status == 429:
        raise TiingoResponseError(f"{ticker}: límite de peticiones de Tiingo alcanzado (HTTP 429). Espera y reintenta.")
    if status != 200:
        raise TiingoResponseError(f"{ticker}: respuesta inesperada de Tiingo (HTTP {status}). Respuesta: {snippet!r}")
    if not body.strip():
        raise TiingoResponseError(f"{ticker}: Tiingo devolvió una respuesta vacía.")
    text = body.decode("utf-8", errors="strict") if _is_utf8(body) else None
    if text is None:
        raise TiingoResponseError(f"{ticker}: la respuesta no es texto UTF-8.")
    first = text.lstrip("﻿").splitlines()[0].strip()
    if first.startswith(("{", "[", "<")) or "error" in first.lower():
        raise TiingoResponseError(f"{ticker}: Tiingo devolvió un mensaje en lugar de un CSV: {snippet!r}")


def _is_utf8(body: bytes) -> bool:
    try:
        body.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def download_ticker(
    ticker: str,
    start: date,
    end: date,
    *,
    key: str,
    raw_dir: Path = RAW_DIR,
    fetch: Fetcher = urllib_fetch,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> DownloadRecord:
    ticker = validate_ticker(ticker)
    url = build_url(ticker, start, end)
    headers = {"Authorization": f"Token {key}", "Accept": "text/csv", "User-Agent": f"ARGOS/{__version__}"}
    try:
        status, _resp_headers, body = fetch(url, headers)
    except TiingoError as exc:
        raise type(exc)(scrub(str(exc), key)) from None
    except Exception as exc:  # cualquier fallo de red: mensaje sin la clave
        raise TiingoResponseError(f"{ticker}: error de red: {scrub(str(exc), key)}") from None
    check_response(ticker, status, body, key)
    if key.encode() in body:
        raise TiingoResponseError(f"{ticker}: la respuesta contiene la clave; no se guarda.")

    # Validación completa del contenido ANTES de guardar (el fichero guardado será exactamente `body`).
    parsed = parse_raw(body.decode("utf-8"), f"{ticker} (respuesta de Tiingo)", start, end)

    moment = now()
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{ticker}_{start}_{end}_{stamp}.csv"
    try:
        with path.open("xb") as fh:  # "x": falla si ya existe; nunca se sobrescribe un original
            fh.write(body)
    except FileExistsError:
        raise TiingoError(f"{ticker}: ya existe {path.name}; los originales nunca se sobrescriben.") from None
    record = DownloadRecord(
        ticker=ticker, url=url, start=start.isoformat(), end=end.isoformat(),
        downloaded_at=moment.isoformat(timespec="seconds"), raw_file=path.name,
        sha256=hashlib.sha256(body).hexdigest(), bytes=len(body), rows=len(parsed.rows),
        first_date=parsed.rows[0].date.isoformat(), last_date=parsed.rows[-1].date.isoformat(),
        http_status=status, argos_version=__version__,
    )
    with (raw_dir / MANIFEST).open("a", encoding="utf-8") as fh:
        fh.write(record.to_json() + "\n")
    return record


# ------------------------------------------------------------------ lectura y validación del original


@dataclass
class RawRow:
    line: int
    date: date
    values: dict[str, str]  # texto literal de cada columna, sin reformatear


@dataclass
class RawSeries:
    rows: list[RawRow]
    splits: list[tuple[date, str]] = field(default_factory=list)
    dividends_per_year: dict[int, int] = field(default_factory=dict)


def _num(text: str, col: str, line: int, where: str) -> float:
    t = (text or "").strip()
    if t == "":
        raise RawDataError(f"{where}, línea {line}: '{col}' está vacío. No se rellena: revisa la descarga.")
    try:
        v = float(t)
    except ValueError:
        raise RawDataError(f"{where}, línea {line}: '{col}' = {t!r} no es un número.") from None
    if not math.isfinite(v):
        raise RawDataError(f"{where}, línea {line}: '{col}' = {t!r} no es un número finito.")
    return v


def parse_raw(text: str, where: str, start: date | None = None, end: date | None = None) -> RawSeries:
    """Lee un CSV original de Tiingo y comprueba que es completo y coherente. No modifica nada."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in RAW_COLUMNS if c not in header]
    if missing:
        raise RawDataError(f"{where}: faltan columnas {missing}. Cabecera recibida: {header}.")
    if len(set(header)) != len(header):
        raise RawDataError(f"{where}: columnas repetidas en la cabecera: {header}.")

    rows: list[RawRow] = []
    seen: dict[date, int] = {}
    splits: list[tuple[date, str]] = []
    dividends: Counter = Counter()
    for line, rec in enumerate(reader, start=2):
        if None in rec or any(v is None for v in rec.values()):
            raise RawDataError(f"{where}, línea {line}: número de campos incorrecto (¿respuesta cortada?).")
        rec = {k.strip(): (v or "").strip() for k, v in rec.items()}
        m = _DATE_RE.match(rec["date"])
        if not m:
            raise RawDataError(f"{where}, línea {line}: fecha {rec['date']!r} con formato inesperado.")
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            raise RawDataError(f"{where}, línea {line}: la fecha {rec['date']!r} no existe.") from None
        if d in seen:
            raise RawDataError(f"{where}, línea {line}: la fecha {d} ya aparece en la línea {seen[d]}.")
        if rows and d < rows[-1].date:
            raise RawDataError(f"{where}, línea {line}: fechas desordenadas ({rows[-1].date} → {d}).")
        if (start and d < start) or (end and d > end):
            raise RawDataError(f"{where}, línea {line}: fecha {d} fuera del rango pedido {start} → {end}.")
        seen[d] = line

        nums = {c: _num(rec[c], c, line, where) for c in RAW_COLUMNS if c != "date"}
        for c in ("open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow", "adjClose"):
            if nums[c] <= 0:
                raise RawDataError(f"{where}, línea {line}: '{c}' = {rec[c]} no es un precio positivo.")
        for c in ("volume", "adjVolume", "divCash"):
            if nums[c] < 0:
                raise RawDataError(f"{where}, línea {line}: '{c}' = {rec[c]} es negativo.")
        if nums["splitFactor"] <= 0:
            raise RawDataError(f"{where}, línea {line}: splitFactor = {rec['splitFactor']} no es válido.")
        # Mismo factor de ajuste en las cuatro columnas de precio: si no, el ajuste es ambiguo.
        factors = [nums[f"adj{c.capitalize()}"] / nums[c] for c in ("open", "high", "low", "close")]
        if max(factors) / min(factors) - 1 > FACTOR_TOLERANCE:
            raise RawDataError(
                f"{where}, línea {line} ({d}): las columnas ajustadas no usan el mismo factor "
                f"({', '.join(f'{f:.6f}' for f in factors)}). Ajuste ambiguo: no se convierte."
            )
        if nums["splitFactor"] != 1:
            splits.append((d, rec["splitFactor"]))
        if nums["divCash"] > 0:
            dividends[d.year] += 1
        rows.append(RawRow(line=line, date=d, values={c: rec[c] for c in RAW_COLUMNS}))

    if not rows:
        raise RawDataError(f"{where}: no contiene ninguna fila de datos.")
    return RawSeries(rows=rows, splits=splits, dividends_per_year=dict(sorted(dividends.items())))


# ------------------------------------------------------------------ manifiesto


def read_manifest(raw_dir: Path = RAW_DIR) -> list[dict]:
    path = raw_dir / MANIFEST
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_download(ticker: str, raw_dir: Path = RAW_DIR) -> dict:
    entries = [e for e in read_manifest(raw_dir) if e["ticker"] == ticker and e.get("status") == "ok"]
    if not entries:
        raise RawDataError(f"{ticker}: no hay ninguna descarga registrada en {raw_dir / MANIFEST}. Descarga primero.")
    return entries[-1]


# ------------------------------------------------------------------ conversión


@dataclass
class ConversionResult:
    ticker: str
    csv_file: Path
    source_file: Path
    rows: int
    raw_sha256: str
    csv_sha256: str
    splits: list[tuple[date, str]]
    dividends_per_year: dict[int, int]


def convert(
    ticker: str,
    *,
    raw_dir: Path = RAW_DIR,
    csv_dir: Path = CSV_DIR,
    overwrite: bool = False,
    entry: dict | None = None,
) -> ConversionResult:
    ticker = validate_ticker(ticker)
    entry = entry or latest_download(ticker, raw_dir)
    raw_path = raw_dir / entry["raw_file"]
    if not raw_path.is_file():
        raise RawDataError(f"{ticker}: falta el fichero original {raw_path.name}.")
    actual = file_sha256(raw_path)
    if actual != entry["sha256"]:
        raise RawDataError(
            f"{ticker}: el fichero original {raw_path.name} ha cambiado desde la descarga "
            f"(SHA-256 {actual[:12]}… ≠ {entry['sha256'][:12]}…). Los originales no deben modificarse: vuelve a descargar."
        )
    raw_text = raw_path.read_text(encoding="utf-8")
    series = parse_raw(raw_text, raw_path.name, date.fromisoformat(entry["start"]), date.fromisoformat(entry["end"]))

    out_lines = ["date,open,high,low,close,volume"]
    for r in series.rows:
        out_lines.append(",".join([r.date.isoformat(), *(r.values[MAPPING[c]] for c in ("open", "high", "low", "close", "volume"))]))
    content = ("\n".join(out_lines) + "\n").encode("utf-8")

    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_path = csv_dir / f"{ticker}.csv"
    if csv_path.exists() and not overwrite and csv_path.read_bytes() != content:
        raise RawDataError(
            f"{ticker}: ya existe {csv_path.name} con contenido distinto. No se sobrescribe; "
            "usa --sobrescribir si quieres reemplazarlo de forma consciente."
        )
    tmp = csv_path.with_suffix(".csv.tmp")
    tmp.write_bytes(content)
    tmp.replace(csv_path)
    csv_sha = hashlib.sha256(content).hexdigest()

    split_txt = ", ".join(f"{d} (factor {f})" for d, f in series.splits) or "ninguno"
    div_txt = ", ".join(f"{y}: {n}" for y, n in series.dividends_per_year.items()) or "ninguno"
    source = "\n".join([
        f"Fuente: Tiingo (api.tiingo.com), endpoint diario. Licencia de uso personal: no publicar estos datos.",
        f"Ticker: {ticker} · rango pedido: {entry['start']} → {entry['end']} · frecuencia diaria",
        f"Descargado: {entry['downloaded_at']} (UTC) con ARGOS {entry['argos_version']}",
        f"Original intacto: data/raw/tiingo/{entry['raw_file']} · SHA-256 {entry['sha256']}",
        f"Convertido: {csv_path.name} · {len(series.rows)} sesiones · {series.rows[0].date} → {series.rows[-1].date} · SHA-256 {csv_sha}",
        "Conversión mecánica: open←adjOpen, high←adjHigh, low←adjLow, close←adjClose, volume←adjVolume "
        "(texto copiado literalmente; solo se normaliza la fecha a AAAA-MM-DD).",
        "Ajuste: precios ajustados por Tiingo por splits y dividendos (rentabilidad total). ARGOS no puede verificar "
        "el método de ajuste de Tiingo.",
        f"Splits según Tiingo (splitFactor ≠ 1): {split_txt}",
        f"Dividendos por año según Tiingo (divCash > 0): {div_txt}",
    ]) + "\n"
    source_path = csv_dir / f"{ticker}.source.txt"
    source_path.write_text(source, encoding="utf-8")
    return ConversionResult(ticker=ticker, csv_file=csv_path, source_file=source_path, rows=len(series.rows),
                            raw_sha256=entry["sha256"], csv_sha256=csv_sha, splits=series.splits,
                            dividends_per_year=series.dividends_per_year)
