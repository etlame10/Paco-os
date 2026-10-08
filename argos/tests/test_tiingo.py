"""Cadena Tiingo → originales → conversión → CSV de ARGOS → validación.

Nunca se conecta a Internet: `fetch` se sustituye por un Tiingo FALSO que
devuelve respuestas construidas en el propio test. Las cifras son sintéticas.
"""

import hashlib
import json
import subprocess
from datetime import date, datetime, timedelta, timezone

import pytest

from argos.data.providers.csv_provider import CsvProvider
from argos.data.sources import tiingo
from argos.tools import tiingo as cli

KEY = "k" * 32 + "SECRETO" + "9" * 8  # clave ficticia, solo para tests
HEADER = "date,close,high,low,open,volume,adjClose,adjHigh,adjLow,adjOpen,adjVolume,divCash,splitFactor"
START, END = date(2007, 1, 1), date(2025, 12, 31)
FIXED_NOW = lambda: datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731


def tiingo_csv(start=date(2007, 1, 3), end=date(2025, 12, 31), date_fmt="{d}", split_on=None, factor=0.5):
    """CSV con el formato de Tiingo: precios originales y ajustados (factor fijo), un dividendo trimestral."""
    lines, d, p, i = [HEADER], start, 50.0, 0
    while d <= end:
        if d.weekday() < 5:
            p = p * (1.0003 if i % 3 else 0.9998)
            o, h, l, c = round(p, 2), round(p * 1.01, 2), round(p * 0.99, 2), round(p * 1.002, 2)
            div = "0.25" if (d.month in (3, 6, 9, 12) and d.day == 15) else "0.0"
            sf = "2.0" if split_on == d else "1.0"
            lines.append(",".join([date_fmt.format(d=d.isoformat()), f"{c}", f"{h}", f"{l}", f"{o}", "1000000",
                                   f"{c * factor:.6f}", f"{h * factor:.6f}", f"{l * factor:.6f}", f"{o * factor:.6f}",
                                   "2000000", div, sf]))
            i += 1
        d += timedelta(days=1)
    return "\n".join(lines) + "\n"


GOOD = tiingo_csv()


class FakeTiingo:
    """Tiingo falso: registra cada petición y devuelve (status, cabeceras, cuerpo)."""

    def __init__(self, status=200, body=GOOD, per_ticker=None, raise_exc=None):
        self.status, self.body, self.per_ticker, self.raise_exc = status, body, per_ticker or {}, raise_exc
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        if self.raise_exc:
            raise self.raise_exc
        ticker = url.split("/daily/")[1].split("/")[0].upper()
        status, body = self.per_ticker.get(ticker, (self.status, self.body))
        return status, {}, body.encode("utf-8") if isinstance(body, str) else body


def download(tmp_path, fake, ticker="SPY"):
    return tiingo.download_ticker(ticker, START, END, key=KEY, raw_dir=tmp_path / "raw", fetch=fake, now=FIXED_NOW)


def nothing_saved(tmp_path):
    raw = tmp_path / "raw"
    return not raw.exists() or not any(raw.iterdir())


# ----------------------------------------------------------------- clave


def test_missing_key_stops_with_clear_message():
    for env in ({}, {"TIINGO_API_KEY": ""}, {"TIINGO_API_KEY": "   "}):
        with pytest.raises(tiingo.MissingKeyError, match="TIINGO_API_KEY"):
            tiingo.read_api_key(env)
    with pytest.raises(tiingo.MissingKeyError):
        tiingo.read_api_key({"TIINGO_API_KEY": "corta"})
    assert tiingo.read_api_key({"TIINGO_API_KEY": f"  {KEY}\n"}) == KEY


def test_key_is_only_read_from_environment(tmp_path, monkeypatch):
    """Ni un fichero .env ni otras variables sirven como alternativa."""
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    monkeypatch.setenv("TIINGO_TOKEN", KEY)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"TIINGO_API_KEY={KEY}\n")
    with pytest.raises(tiingo.MissingKeyError):
        tiingo.read_api_key()


def test_cli_without_key_exits_before_any_request(monkeypatch, capsys):
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    called = []
    monkeypatch.setattr(tiingo, "download_ticker", lambda *a, **k: called.append(a))
    assert cli.main(["descargar"]) == 2
    assert called == [] and "TIINGO_API_KEY" in capsys.readouterr().out


def test_key_goes_in_header_never_in_url_or_files(tmp_path, capsys):
    fake = FakeTiingo()
    rec = download(tmp_path, fake)
    url, headers = fake.calls[0]
    assert headers["Authorization"] == f"Token {KEY}"
    assert KEY not in url and "token" not in url.lower()
    assert url == ("https://api.tiingo.com/tiingo/daily/spy/prices?startDate=2007-01-01&endDate=2025-12-31"
                   "&format=csv&resampleFreq=daily")
    for f in (tmp_path / "raw").iterdir():
        assert KEY not in f.read_text()
    assert KEY not in rec.to_json() and KEY not in capsys.readouterr().out


def test_network_error_message_never_contains_key(tmp_path):
    fake = FakeTiingo(raise_exc=OSError(f"fallo conectando con token={KEY}"))
    with pytest.raises(tiingo.TiingoResponseError) as exc:
        download(tmp_path, fake)
    assert KEY not in str(exc.value) and "***" in str(exc.value)


# ----------------------------------------------------------------- errores de Tiingo


@pytest.mark.parametrize("status, err, fragment", [
    (401, tiingo.TiingoAuthError, "autenticación"),
    (403, tiingo.TiingoAuthError, "autenticación"),
    (404, tiingo.TiingoResponseError, "no reconoce el ticker"),
    (429, tiingo.TiingoResponseError, "límite de peticiones"),
    (500, tiingo.TiingoResponseError, "HTTP 500"),
])
def test_http_errors_stop_and_save_nothing(tmp_path, status, err, fragment):
    body = json.dumps({"detail": f"Error: invalid token {KEY}"})
    with pytest.raises(err, match=fragment) as exc:
        download(tmp_path, FakeTiingo(status=status, body=body))
    assert KEY not in str(exc.value)
    assert nothing_saved(tmp_path)


@pytest.mark.parametrize("body, fragment", [
    ("", "vacía"),
    ('{"detail": "Error: Ticker not found"}', "mensaje en lugar de un CSV"),
    ("<html><body>Bot check</body></html>", "mensaje en lugar de un CSV"),
    ("Error: You have run over your hourly request allocation", "mensaje en lugar de un CSV"),
    (b"\xff\xfe\x00date", "UTF-8"),
], ids=["vacia", "json", "html", "texto-error", "no-utf8"])
def test_unexpected_200_bodies_are_rejected(tmp_path, body, fragment):
    with pytest.raises(tiingo.TiingoResponseError, match=fragment):
        download(tmp_path, FakeTiingo(body=body))
    assert nothing_saved(tmp_path)


def test_cli_stops_all_downloads_on_auth_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TIINGO_API_KEY", KEY)
    monkeypatch.setattr(tiingo, "RAW_DIR", tmp_path / "raw")
    fake = FakeTiingo(status=401, body="{}")
    real = tiingo.download_ticker
    monkeypatch.setattr(tiingo, "download_ticker", lambda t, s, e, **k: real(t, s, e, fetch=fake, raw_dir=tmp_path / "raw", **k))
    assert cli.main(["descargar"]) == 2
    assert len(fake.calls) == 1  # no sigue con el resto de activos
    assert KEY not in capsys.readouterr().out


# ----------------------------------------------------------------- respuestas incompletas o mal formadas


def corrupt(line_no: int, column: str, value: str, base: str = GOOD) -> str:
    lines = base.splitlines()
    cols = HEADER.split(",")
    parts = lines[line_no - 1].split(",")
    parts[cols.index(column)] = value
    lines[line_no - 1] = ",".join(parts)
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("body, fragment", [
    (GOOD.rsplit("\n", 2)[0][:-15] + "\n", "número de campos"),  # respuesta cortada a mitad de fila
    (GOOD.replace("adjOpen,", "adjOpenX,", 1), "faltan columnas"),
    (GOOD.replace(",divCash,splitFactor", "", 1), "faltan columnas"),
    (HEADER + "\n", "ninguna fila"),
    (corrupt(10, "adjClose", ""), "vacío"),
    (corrupt(10, "adjClose", "abc"), "no es un número"),
    (corrupt(10, "adjClose", "nan"), "finito"),
    (corrupt(10, "close", "-5"), "precio positivo"),
    (corrupt(10, "adjVolume", "-1"), "negativo"),
    (corrupt(10, "splitFactor", "0"), "splitFactor"),
    (corrupt(10, "date", "03/01/2007"), "formato inesperado"),
    (corrupt(10, "date", "2007-02-30"), "no existe"),
    (corrupt(10, "date", "2007-01-03"), "ya aparece"),
    (corrupt(10, "date", "2006-12-29"), "desordenadas"),
    (corrupt(10, "adjHigh", "999.0"), "mismo factor"),
    (tiingo_csv(start=date(2006, 12, 27), end=date(2007, 3, 1)), "fuera del rango"),
], ids=["cortada", "sin-adjOpen", "sin-div-split", "sin-filas", "vacio", "texto", "nan", "precio-negativo",
        "volumen-negativo", "split-0", "fecha-formato", "fecha-inexistente", "fecha-duplicada", "desordenada",
        "factor-ambiguo", "fuera-de-rango"])
def test_malformed_data_is_rejected_not_fixed(tmp_path, body, fragment):
    with pytest.raises(tiingo.RawDataError, match=fragment):
        download(tmp_path, FakeTiingo(body=body))
    assert nothing_saved(tmp_path)


# ----------------------------------------------------------------- descarga correcta


def test_successful_download_keeps_original_bytes_and_manifest(tmp_path):
    rec = download(tmp_path, FakeTiingo())
    raw = tmp_path / "raw" / rec.raw_file
    assert raw.name == "SPY_2007-01-01_2025-12-31_20261008T120000Z.csv"
    assert raw.read_bytes() == GOOD.encode()  # byte a byte
    assert rec.sha256 == hashlib.sha256(GOOD.encode()).hexdigest()
    (entry,) = tiingo.read_manifest(tmp_path / "raw")
    assert entry["sha256"] == rec.sha256 and entry["downloaded_at"] == "2026-10-08T12:00:00+00:00"
    assert entry["rows"] == len(GOOD.splitlines()) - 1 and entry["first_date"] == "2007-01-03"
    assert entry["start"] == "2007-01-01" and entry["end"] == "2025-12-31"


def test_original_is_never_overwritten(tmp_path):
    download(tmp_path, FakeTiingo())
    with pytest.raises(tiingo.TiingoError, match="nunca se sobrescriben"):
        download(tmp_path, FakeTiingo())
    assert len(tiingo.read_manifest(tmp_path / "raw")) == 1


def test_other_tickers_continue_after_non_auth_error(tmp_path, monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", KEY)
    fake = FakeTiingo(per_ticker={"KO": (404, '{"detail":"not found"}')})
    real = tiingo.download_ticker
    monkeypatch.setattr(tiingo, "download_ticker",
                        lambda t, s, e, **k: real(t, s, e, fetch=fake, raw_dir=tmp_path / "raw", now=FIXED_NOW, key=KEY))
    assert cli.main(["descargar"]) == 1
    assert [e["ticker"] for e in tiingo.read_manifest(tmp_path / "raw")] == ["SPY", "AAPL", "XOM"]


def test_only_protocol_assets_and_dates(monkeypatch):
    monkeypatch.setenv("TIINGO_API_KEY", KEY)
    assert cli.main(["descargar", "--tickers", "MSFT"]) == 2
    tickers, start, end = cli._plan("EXP-001", None, False)
    assert tickers == ["SPY", "KO", "AAPL", "XOM"] and (start, end) == (START, END)
    assert cli._plan("EXP-001", None, True)[0][-2:] == ["GLD", "EFA"]


# ----------------------------------------------------------------- conversión


def test_conversion_is_mechanical(tmp_path):
    body = tiingo_csv(date_fmt="{d}T00:00:00.000Z", split_on=date(2014, 6, 9))
    rec = download(tmp_path, FakeTiingo(body=body), "AAPL")
    res = tiingo.convert("AAPL", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    out = (tmp_path / "csv" / "AAPL.csv").read_text().splitlines()
    src = body.splitlines()
    cols = HEADER.split(",")
    assert out[0] == "date,open,high,low,close,volume"
    assert len(out) == len(src)
    for o, s in zip(out[1:], src[1:]):  # copia literal del texto de las columnas ajustadas
        v = dict(zip(cols, s.split(",")))
        assert o == ",".join([v["date"][:10], v["adjOpen"], v["adjHigh"], v["adjLow"], v["adjClose"], v["adjVolume"]])
    assert res.splits == [(date(2014, 6, 9), "2.0")]
    assert res.dividends_per_year[2010] == 4
    # El original sigue intacto.
    assert hashlib.sha256((tmp_path / "raw" / rec.raw_file).read_bytes()).hexdigest() == rec.sha256


def test_source_txt_records_provenance(tmp_path):
    rec = download(tmp_path, FakeTiingo(), "KO")
    tiingo.convert("KO", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    txt = (tmp_path / "csv" / "KO.source.txt").read_text()
    for needle in ("Tiingo", "uso personal", rec.sha256, "2026-10-08T12:00:00+00:00", "adjClose",
                   "2007-01-01 → 2025-12-31", "splits y dividendos", "Dividendos por año"):
        assert needle in txt, needle
    csv_sha = hashlib.sha256((tmp_path / "csv" / "KO.csv").read_bytes()).hexdigest()
    assert csv_sha in txt
    assert KEY not in txt


def test_conversion_refuses_tampered_original(tmp_path):
    rec = download(tmp_path, FakeTiingo())
    raw = tmp_path / "raw" / rec.raw_file
    raw.write_text(raw.read_text().replace("1000000", "1000001", 1))
    with pytest.raises(tiingo.RawDataError, match="ha cambiado"):
        tiingo.convert("SPY", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    assert not (tmp_path / "csv" / "SPY.csv").exists()


def test_conversion_without_download_or_missing_original(tmp_path):
    with pytest.raises(tiingo.RawDataError, match="Descarga primero"):
        tiingo.convert("SPY", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    rec = download(tmp_path, FakeTiingo())
    (tmp_path / "raw" / rec.raw_file).unlink()
    with pytest.raises(tiingo.RawDataError, match="falta el fichero original"):
        tiingo.convert("SPY", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")


def test_conversion_does_not_silently_overwrite(tmp_path):
    download(tmp_path, FakeTiingo())
    kw = dict(raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    tiingo.convert("SPY", **kw)
    tiingo.convert("SPY", **kw)  # mismo contenido: no hay problema
    (tmp_path / "csv" / "SPY.csv").write_text("date,open,high,low,close,volume\n")
    with pytest.raises(tiingo.RawDataError, match="--sobrescribir"):
        tiingo.convert("SPY", **kw)
    tiingo.convert("SPY", overwrite=True, **kw)
    assert len((tmp_path / "csv" / "SPY.csv").read_text().splitlines()) > 4000


def test_full_chain_produces_valid_argos_csv(tmp_path, monkeypatch, capsys):
    """Tiingo (falso) → original → conversión → lector de ARGOS → control de integridad del protocolo."""
    monkeypatch.setenv("TIINGO_API_KEY", KEY)
    raw, csvd = tmp_path / "raw", tmp_path / "csv"
    monkeypatch.setattr(tiingo, "RAW_DIR", raw)
    monkeypatch.setattr(tiingo, "CSV_DIR", csvd)
    monkeypatch.setenv("ARGOS_CSV_DIR", str(csvd))
    real_dl, real_cv = tiingo.download_ticker, tiingo.convert
    monkeypatch.setattr(tiingo, "download_ticker",
                        lambda t, s, e, **k: real_dl(t, s, e, fetch=FakeTiingo(), raw_dir=raw, now=FIXED_NOW, key=KEY))
    monkeypatch.setattr(tiingo, "convert", lambda t, **k: real_cv(t, raw_dir=raw, csv_dir=csvd, overwrite=k.get("overwrite", False)))
    assert cli.main(["descargar"]) == 0
    assert cli.main(["convertir"]) == 0  # incluye el control de integridad con los requisitos de EXP-001
    out = capsys.readouterr().out
    assert out.count("superado") == 4 and KEY not in out
    h = CsvProvider(csvd).get_price_history("XOM")
    assert h.provenance.is_simulated is False and h.bars[0].date == date(2007, 1, 3)


def test_short_download_is_saved_but_flagged_by_quality_check(tmp_path, monkeypatch, capsys):
    """Si Tiingo devuelve menos años de los pedidos, no se rellena: el control de integridad lo bloquea."""
    short = tiingo_csv(start=date(2015, 1, 2))
    download(tmp_path, FakeTiingo(body=short))
    tiingo.convert("SPY", raw_dir=tmp_path / "raw", csv_dir=tmp_path / "csv")
    from argos.data.check import main as check_main

    assert check_main(["--dir", str(tmp_path / "csv"), "--protocolo", "EXP-001", "SPY"]) == 1
    assert "se necesita desde 2007-01-01" in capsys.readouterr().out


# ----------------------------------------------------------------- garantías del repositorio


def test_protocol_exp001_unchanged(root):
    """El protocolo pre-registrado sigue siendo exactamente el del commit 6b230de."""
    sha = hashlib.sha256((root / "protocols" / "EXP-001.json").read_bytes()).hexdigest()
    assert sha == "7f553e110fff59245a96504bdd0107b179550164eaf3800cbe8664f34cc98cce"


def test_private_data_and_keys_are_git_ignored(root):
    paths = ["data/raw/tiingo/SPY_x.csv", "data/raw/tiingo/manifest.jsonl", "data/csv/SPY.csv",
             "data/csv/SPY.source.txt", ".env", ".env.local", "tiingo.key"]
    res = subprocess.run(["git", "check-ignore", "--no-index", *paths], cwd=root, capture_output=True, text=True)
    assert sorted(res.stdout.split()) == sorted(paths)


def test_no_key_in_source_code_or_frontend(root):
    for folder in ("argos", "web"):
        for f in (root / folder).rglob("*"):
            if f.is_file() and f.suffix in {".py", ".js", ".html", ".css", ".json"}:
                text = f.read_text(encoding="utf-8", errors="ignore")
                assert "Token " not in text or f.name == "tiingo.py", f
                assert "TIINGO_API_KEY=" not in text, f


# ----------------------------------------------------------------- TLS: siempre verificado


import re as _re
import shutil as _shutil
import ssl
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

INSECURE_PATTERNS = ["CERT_NONE", "check_hostname = False", "check_hostname=False", "_create_unverified_context",
                     "verify=False", "PYTHONHTTPSVERIFY", "OP_NO_TLSv1_2"]


def test_tls_context_always_verifies():
    ctx = tiingo.tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert ctx.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert ctx.cert_store_stats()["x509_ca"] > 100  # raíces de certifi cargadas


def test_fetch_uses_the_verified_context(monkeypatch):
    seen = {}

    class Resp:
        status, headers = 200, {}
        def read(self): return b"date\n"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None, context=None):
        seen["ctx"], seen["url"] = context, req.full_url
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    tiingo.urllib_fetch("https://api.tiingo.com/x", {"Authorization": f"Token {KEY}"})
    assert isinstance(seen["ctx"], ssl.SSLContext)
    assert seen["ctx"].verify_mode == ssl.CERT_REQUIRED and seen["ctx"].check_hostname


@pytest.mark.parametrize("reason", [
    ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired"),
    ssl.SSLError(1, "handshake failure"),
], ids=["caducado", "handshake"])
def test_tls_errors_are_reported_clearly_without_key(monkeypatch, tmp_path, reason):
    def boom(req, timeout=None, context=None):
        raise urllib.error.URLError(reason)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(tiingo.TiingoTLSError) as exc:
        tiingo.download_ticker("SPY", START, END, key=KEY, raw_dir=tmp_path / "raw", now=FIXED_NOW)
    msg = str(exc.value)
    assert "no se conecta sin verificar" in msg and "diagnosticar-tls" in msg and "reloj" in msg
    assert KEY not in msg
    assert nothing_saved(tmp_path)


def test_cli_stops_on_first_tls_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TIINGO_API_KEY", KEY)
    calls = []

    def tls_fail(t, s, e, **k):
        calls.append(t)
        raise tiingo.TiingoTLSError("certificado no verificable")

    monkeypatch.setattr(tiingo, "download_ticker", tls_fail)
    assert cli.main(["descargar"]) == 2
    assert calls == ["SPY"]
    assert "Se detiene la descarga" in capsys.readouterr().out


@pytest.fixture
def untrusted_https_server(tmp_path):
    """Servidor HTTPS en localhost con un certificado autofirmado (no confiable)."""
    if not _shutil.which("openssl"):
        pytest.skip("openssl no disponible para generar el certificado de prueba")
    cert, keyf = tmp_path / "c.pem", tmp_path / "k.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(keyf), "-out", str(cert),
                    "-days", "2", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"],
                   check=True, capture_output=True)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(GOOD.encode())

        def log_message(self, *a):
            pass

    server = HTTPServer(("localhost", 0), Handler)
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(cert, keyf)
    server.socket = sctx.wrap_socket(server.socket, server_side=True)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"https://localhost:{server.server_address[1]}/tiingo/daily/spy/prices"
    server.shutdown()


def test_real_connection_rejects_untrusted_certificate(untrusted_https_server):
    """Prueba de extremo a extremo: con un certificado no confiable, la conexión se RECHAZA."""
    with pytest.raises(tiingo.TiingoTLSError, match="no se conecta sin verificar"):
        tiingo.urllib_fetch(untrusted_https_server, {"Authorization": f"Token {KEY}"}, timeout=10)


def test_diagnose_tls_never_disables_verification():
    contexts = []

    def ok_handshake(host, port, timeout, ctx):
        contexts.append(ctx)
        return {"subject": ((("commonName", "api.tiingo.com"),),), "issuer": ((("organizationName", "CA Ejemplo"),),),
                "notAfter": "Jan  1 00:00:00 2027 GMT"}

    ok, lines = tiingo.diagnose_tls(handshake=ok_handshake)
    assert ok and any("[OK]" in l for l in lines) and "puede conectar" in lines[-1]
    assert len(contexts) == 2 and all(c.verify_mode == ssl.CERT_REQUIRED and c.check_hostname for c in contexts)
    assert any("Fecha y hora de este PC" in l for l in lines) and any("certifi" in l for l in lines)


def test_diagnose_tls_conclusions():
    expired = ssl.SSLCertVerificationError(1, "certificate verify failed")
    expired.verify_message, expired.verify_code = "certificate has expired", 10

    def always_fail(host, port, timeout, ctx):
        raise expired

    ok, lines = tiingo.diagnose_tls(handshake=always_fail)
    assert not ok and "certificate has expired" in " ".join(lines) and "fecha y hora" in lines[-1]

    calls = []

    def only_system(host, port, timeout, ctx):  # 1.ª llamada = certifi (falla), 2.ª = sistema (funciona)
        calls.append(ctx)
        if len(calls) == 1:
            raise expired
        return {"subject": (), "issuer": ()}

    ok, lines = tiingo.diagnose_tls(handshake=only_system)
    assert not ok and "antivirus o proxy" in lines[-1]


def test_cli_diagnose_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(tiingo, "diagnose_tls", lambda: (True, ["todo bien"]))
    assert cli.main(["diagnosticar-tls"]) == 0
    monkeypatch.setattr(tiingo, "diagnose_tls", lambda: (False, ["falla"]))
    assert cli.main(["diagnosticar-tls"]) == 1
    assert "sin clave" in capsys.readouterr().out


def test_no_insecure_tls_anywhere_in_source(root):
    for f in (root / "argos").rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        for pat in INSECURE_PATTERNS:
            assert pat not in text, f"{f.name} contiene {pat!r}"


def test_certifi_is_pinned(root):
    reqs = (root / "requirements.txt").read_text()
    assert _re.search(r"^certifi==\d{4}\.\d+\.\d+$", reqs, _re.M)
