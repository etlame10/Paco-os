"""API web de ARGOS. Solo lectura: todas las rutas son GET y ninguna opera.

Arranque:  uvicorn argos.api.app:app --reload   (desde la carpeta argos/)
"""

from __future__ import annotations

from pathlib import Path

from datetime import date

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from argos import __version__
from argos.core.models import AnalysisReport
from argos.core.safety import DISCLAIMER, LIVE_TRADING_ENABLED
from argos.backtest.models import BacktestConfig, BacktestReport
from argos.backtest.service import BacktestService
from argos.data.base import DataProviderError, TickerNotFoundError
from argos.pipeline import AnalysisService
from argos.strategy import examples as _examples  # noqa: F401  (registra estrategias)
from argos.strategy.base import available_strategies, strategy_catalog

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(service: AnalysisService | None = None, backtests: BacktestService | None = None) -> FastAPI:
    service = service or AnalysisService()
    backtests = backtests or BacktestService(registry=service.registry)
    app = FastAPI(title="ARGOS", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.url.path.startswith("/api/docs"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            )
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "broker_connected": False,
            "disclaimer": DISCLAIMER,
        }

    @app.get("/api/providers")
    def providers() -> dict:
        return {
            "providers": [
                {**p.describe(), "tickers": p.list_tickers()} for p in service.registry.providers
            ]
        }

    @app.get("/api/strategies")
    def strategies() -> dict:
        return {"strategies": available_strategies(), "note": "Solo generan señales hipotéticas para backtesting; no ejecutan nada."}

    @app.get("/api/backtest/options")
    def backtest_options() -> dict:
        return {
            "tickers": [
                {"ticker": t, "provider": p.name, "is_simulated": p.is_simulated or t.startswith("DEMO-")}
                for p in backtests.registry.providers
                for t in (p.list_tickers() or [])
            ],
            "strategies": [s for s in strategy_catalog() if s["name"] != "buy_and_hold"],
            "defaults": {"capital": 10000, "commission_percent": 0.1, "slippage_percent": 0.05},
            "note": "Simulación histórica. No ejecuta operaciones.",
        }

    @app.get("/api/backtest", response_model=BacktestReport)
    def backtest(
        request: Request,
        ticker: str,
        strategy: str = "sma_crossover",
        capital: float = Query(10_000, gt=0, le=1e12),
        commission_percent: float = Query(0.1, ge=0, le=5, description="0.1 = 0,1% por operación"),
        slippage_percent: float = Query(0.05, ge=0, le=5, description="0.05 = 0,05% por ejecución"),
        start: date | None = None,
        end: date | None = None,
    ):
        reserved = {"ticker", "strategy", "capital", "commission_percent", "slippage_percent", "start", "end"}
        params = {k: v for k, v in request.query_params.items() if k not in reserved}
        try:
            config = BacktestConfig(
                initial_capital=capital,
                commission_pct=commission_percent / 100,
                slippage_pct=slippage_percent / 100,
                start=start,
                end=end,
            )
            return backtests.run(ticker, strategy, params, config)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except DataProviderError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except ValueError as exc:  # parámetros, fechas, look-ahead, validación
            raise HTTPException(status_code=400, detail=_clean(exc))

    @app.get("/api/analyze/{ticker}", response_model=AnalysisReport)
    def analyze(ticker: str):
        try:
            return service.analyze(ticker)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except DataProviderError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.exception_handler(Exception)
    async def unhandled(_request, _exc):
        return JSONResponse(status_code=500, content={"detail": "Error interno de ARGOS."})

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def _clean(exc: Exception) -> str:
    """Mensaje legible para errores de validación de pydantic."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        return "; ".join(str(e.get("msg", "")).removeprefix("Value error, ") for e in errors())
    return str(exc)


app = create_app()
