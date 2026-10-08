import pytest
from fastapi.testclient import TestClient

from argos.api.app import create_app
from argos.data.providers.demo import DemoProvider
from argos.experiments.registry import ExperimentRegistry
from argos.data.registry import ProviderRegistry
from argos.pipeline import AnalysisService


@pytest.fixture(scope="module")
def registry_path(tmp_path_factory):
    return tmp_path_factory.mktemp("reg") / "registry.jsonl"


@pytest.fixture(scope="module")
def client(registry_path):
    return TestClient(create_app(
        AnalysisService(registry=ProviderRegistry([DemoProvider()])),
        experiments=ExperimentRegistry(registry_path),
    ))


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


#: Única ruta que escribe algo: una línea en el registro LOCAL de experimentos.
WRITE_ROUTES = {"/api/experiments": {"GET", "POST"}}


def test_api_is_read_only(client):
    """Ninguna ruta acepta PUT/PATCH/DELETE; solo el registro de experimentos acepta POST.
    Ninguna ruta habla de órdenes, operaciones ni brokers."""
    for route in client.app.routes:
        methods = getattr(route, "methods", None) or set()
        allowed = WRITE_ROUTES.get(route.path, {"GET", "HEAD"}) | {"HEAD"}
        assert methods <= allowed, f"{route.path} acepta {methods}"
        for word in ("order", "orden", "trade", "buy", "sell", "broker", "execute"):
            assert word not in route.path.lower(), route.path
    for method in ("post", "put", "delete", "patch"):
        assert getattr(client, method)("/api/analyze/DEMO-ALCISTA").status_code == 405


# ----------------------------------------------------------------- backtest


def test_backtest_options(client):
    opts = client.get("/api/backtest/options").json()
    assert all(t["is_simulated"] for t in opts["tickers"])
    names = [s["name"] for s in opts["strategies"]]
    assert names == ["sma_crossover"]
    assert opts["strategies"][0]["params"]["fast"]["default"] == 50


def test_backtest_endpoint_runs_demo(client):
    r = client.get("/api/backtest", params={"ticker": "DEMO-LATERAL", "strategy": "sma_crossover",
                                            "capital": 5000, "commission_percent": 0.2, "slippage_percent": 0.1,
                                            "fast": 20, "slow": 50})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["strategy"]["metrics"]["initial_capital"] == 5000
    assert body["transparency"]["strategy"]["params"] == {"fast": 20, "slow": 50}
    assert "0.200%" in body["transparency"]["commission"]
    assert body["is_simulated_data"] is True
    assert body["lookahead_audit"]["passed"] is True
    assert body["live_trading_enabled"] is False
    assert "NO PREDICCIÓN" in body["warning"]


@pytest.mark.parametrize(
    "params, status",
    [
        ({"ticker": "AAPL"}, 404),
        ({"ticker": "DEMO-LATERAL", "fast": 200, "slow": 50}, 400),
        ({"ticker": "DEMO-LATERAL", "strategy": "no_existe"}, 400),
        ({"ticker": "DEMO-LATERAL", "start": "2025-06-01", "end": "2025-01-01"}, 400),
        ({"ticker": "DEMO-LATERAL", "start": "2025-13-01"}, 422),
        ({"ticker": "DEMO-LATERAL", "start": "2000-01-01", "end": "2001-01-01"}, 422),
        ({"ticker": "DEMO-LATERAL", "capital": -5}, 422),
        ({"ticker": "DEMO-LATERAL", "commission_percent": 50}, 422),
        ({"ticker": "<x>"}, 400),
    ],
)
def test_backtest_endpoint_errors(client, params, status):
    r = client.get("/api/backtest", params=params)
    assert r.status_code == status, r.text
    assert r.json()["detail"]


# ----------------------------------------------------------------- registro de experimentos


def test_save_and_list_experiment(client, registry_path):
    before = client.get("/api/experiments").json()["count"]
    r = client.post("/api/experiments", json={"ticker": "DEMO-LATERAL", "params": {"fast": 20, "slow": 50},
                                              "capital": 5000, "commission_percent": 0.2})
    assert r.status_code == 201, r.text
    rec = r.json()["record"]
    assert rec["ticker"] == "DEMO-LATERAL" and rec["params"] == {"fast": 20, "slow": 50}
    assert rec["initial_capital"] == 5000 and rec["commission_pct"] == pytest.approx(0.002)
    assert rec["dry_run"] is True and rec["is_simulated_data"] is True  # datos demo: nunca cuenta como resultado
    assert rec["argos_version"] and rec["recorded_at"] and rec["strategy_metrics"]["n_trades"] >= 0
    listing = client.get("/api/experiments").json()
    assert listing["count"] == before + 1 and listing["records"][0]["record_id"] == rec["record_id"]
    assert registry_path.read_text().count("\n") == before + 1


def test_save_experiment_ignores_client_metrics(client):
    """Las métricas siempre las calcula el servidor; los campos extra se ignoran."""
    r = client.post("/api/experiments", json={"ticker": "DEMO-LATERAL", "strategy_metrics": {"total_return": 99}})
    assert r.status_code == 201
    assert r.json()["record"]["strategy_metrics"]["total_return"] != 99


def test_save_experiment_validation(client):
    assert client.post("/api/experiments", json={"ticker": "AAPL"}).status_code == 404
    assert client.post("/api/experiments", json={"ticker": "DEMO-LATERAL", "capital": -1}).status_code == 422
    assert client.put("/api/experiments", json={}).status_code == 405
    assert client.delete("/api/experiments").status_code == 405


def test_browser_cannot_forge_experiment_records(client):
    """Desde el navegador no se puede crear un resultado de EXP-001 ni marcarlo como real."""
    forged = {"ticker": "DEMO-LATERAL", "experiment_id": "EXP-001", "protocol_sha256": "7f553e11" + "0" * 56,
              "period_name": "fuera_de_muestra", "dry_run": False, "is_simulated_data": False,
              "strategy_metrics": {"total_return": 9.9}, "verdict": "funciona"}
    r = client.post("/api/experiments", json=forged)
    assert r.status_code == 201
    rec = r.json()["record"]
    assert rec["experiment_id"] is None and rec["protocol_sha256"] is None and rec["period_name"] is None
    assert rec["dry_run"] is True and rec["is_simulated_data"] is True
    assert rec["strategy_metrics"]["total_return"] != 9.9 and rec["verdict"] != "funciona"
