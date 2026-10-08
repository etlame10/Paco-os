"""Verificaciones de seguridad de la fase 1: sin operativa real y sin secretos en el frontend."""

import re

import pytest

from argos.core import safety

BROKER_LIBS = [
    "alpaca", "ib_insync", "ibapi", "ccxt", "binance", "oandapyV20", "MetaTrader5",
    "robin_stocks", "tda", "schwab", "degiro", "xtb", "krakenex", "coinbase", "tradingview",
]
SECRET_PATTERNS = [
    r"api[_-]?key", r"secret", r"password", r"bearer\s", r"authorization",
    r"sk-[A-Za-z0-9]{10,}", r"sb_secret_", r"service_role", r"AKIA[0-9A-Z]{16}",
    r"token\s*[:=]", r"process\.env", r"import\.meta\.env",
]


def test_live_trading_is_disabled():
    assert safety.LIVE_TRADING_ENABLED is False
    with pytest.raises(safety.LiveTradingDisabledError):
        safety.assert_no_live_trading()


def test_no_broker_libraries_or_order_code(root):
    lib_re = re.compile(r"^\s*(import|from)\s+(" + "|".join(BROKER_LIBS) + r")\b", re.M | re.I)
    order_re = re.compile(r"def\s+(place|submit|send|execute)_?order", re.I)
    for path in (root / "argos").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert not lib_re.search(src), f"{path} importa una librería de broker"
        assert not order_re.search(src), f"{path} define una función de órdenes"
    reqs = (root / "requirements.txt").read_text().lower()
    for lib in BROKER_LIBS:
        assert lib.lower() not in reqs


def test_no_secrets_in_frontend(root):
    files = [p for p in (root / "web").rglob("*") if p.is_file()]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in SECRET_PATTERNS:
            assert not re.search(pat, text, re.I), f"{path.name} contiene un patrón sospechoso: {pat}"


def test_frontend_only_talks_to_own_api(root):
    scripts = sorted((root / "web").glob("*.js"))
    assert [p.name for p in scripts] == ["app.js", "backtest.js"]
    for path in scripts:
        js = path.read_text(encoding="utf-8")
        urls = set(re.findall(r"https?://[^\s\"'`)]+", js))
        assert urls <= {"http://www.w3.org/2000/svg"}, (path.name, urls)  # solo el namespace SVG
        fetches = re.findall(r"fetch\(\s*[`\"']([^`\"']+)", js)
        assert all(u.startswith("/api/") for u in fetches), (path.name, fetches)
        assert "method:" not in js and "POST" not in js, path.name  # el frontend solo hace GET


def test_backtest_ui_labels_history_not_prediction(root):
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    assert "RESULTADO HISTÓRICO · NO ES UNA PREDICCIÓN" in html
    assert 'id="bt-demo-banner"' in html


def test_frontend_marks_simulated_data(root):
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "app.js").read_text(encoding="utf-8")
    assert 'id="demo-banner"' in html and "DATOS DE DEMOSTRACIÓN" in html
    assert "is_simulated" in js and "DATOS DEMO" in js
    assert "Operativa real: DESACTIVADA" in html
