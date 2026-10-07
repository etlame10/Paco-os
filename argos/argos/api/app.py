"""API web de ARGOS. Solo lectura: todas las rutas son GET y ninguna opera.

Arranque:  uvicorn argos.api.app:app --reload   (desde la carpeta argos/)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from argos import __version__
from argos.core.models import AnalysisReport
from argos.core.safety import DISCLAIMER, LIVE_TRADING_ENABLED
from argos.data.base import DataProviderError, TickerNotFoundError
from argos.pipeline import AnalysisService
from argos.strategy import examples as _examples  # noqa: F401  (registra estrategias)
from argos.strategy.base import available_strategies

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(service: AnalysisService | None = None) -> FastAPI:
    service = service or AnalysisService()
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
        return {"strategies": available_strategies(), "note": "Solo para backtesting futuro; no ejecutan nada."}

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


app = create_app()
