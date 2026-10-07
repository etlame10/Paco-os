import pytest
from fastapi.testclient import TestClient

from argos.api.app import create_app
from argos.data.providers.demo import DemoProvider
from argos.data.registry import ProviderRegistry
from argos.pipeline import AnalysisService


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(AnalysisService(registry=ProviderRegistry([DemoProvider()]))))


def test_health_reports_no_trading(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["live_trading_enabled"] is False
    assert h["broker_connected"] is False


def test_index_served_with_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ARGOS" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/app.js").status_code == 200


def test_analyze_demo_ticker(client):
    r = client.get("/api/analyze/DEMO-ALCISTA")
    assert r.status_code == 200
    body = r.json()
    assert body["provenance"]["is_simulated"] is True
    assert body["live_trading_enabled"] is False
    assert body["conclusion"]["factors"]
    assert body["fundamental"]["available"] is False


def test_real_ticker_without_provider_is_404_not_invented(client):
    r = client.get("/api/analyze/AAPL")
    assert r.status_code == 404
    assert "no se inventa" in r.json()["detail"]


def test_invalid_ticker_is_400(client):
    assert client.get("/api/analyze/%3Cscript%3E").status_code == 400


def test_providers_lists_demo_as_simulated(client):
    providers = client.get("/api/providers").json()["providers"]
    assert providers == [{"name": "demo", "is_simulated": True, "tickers": DemoProvider().list_tickers()}]


def test_api_is_read_only(client):
    """No hay ninguna ruta que acepte POST/PUT/PATCH/DELETE ni que hable de órdenes."""
    for route in client.app.routes:
        methods = getattr(route, "methods", None) or set()
        assert methods <= {"GET", "HEAD"}, f"{route.path} acepta {methods}"
        for word in ("order", "orden", "trade", "buy", "sell", "broker", "execute"):
            assert word not in route.path.lower(), route.path
    for method in ("post", "put", "delete", "patch"):
        assert getattr(client, method)("/api/analyze/DEMO-ALCISTA").status_code == 405
