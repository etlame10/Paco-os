# ARGOS

Sistema personal de análisis de mercados. **Fase 1: cimientos.**

ARGOS no se limita a decir "compra" o "vende": separa siempre lo que **sabemos** (datos), lo que **calculamos** (indicadores), lo que **creemos que significa** (interpretación) y la **evaluación final** (conclusión), y te enseña de dónde sale cada cosa.

> ⚠ ARGOS **no opera con dinero real**, no está conectado a ningún broker y no se inventa datos. Ninguna señal o conclusión garantiza cómo se comportará el mercado. No es asesoramiento financiero.

## Puesta en marcha

Requisitos: Python 3.11 o superior.

```bash
cd argos
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest                              # ejecuta los tests
uvicorn argos.api.app:app --reload  # arranca ARGOS
```

Abre <http://localhost:8000> y analiza un ticker de demostración (`DEMO-ALCISTA`, `DEMO-BAJISTA`, `DEMO-LATERAL`, `DEMO-VOLATIL`). La documentación interactiva de la API está en `/api/docs`.

## Datos

| Fuente | Qué es | ¿Real? |
| --- | --- | --- |
| `demo` | Series generadas por ordenador para **empresas ficticias** (`DEMO-*`). Deterministas y con fechas fijas en el pasado. | ❌ Simulado, marcado en toda la interfaz |
| `csv` | Ficheros `data/csv/<TICKER>.csv` con columnas `date,open,high,low,close,volume` que tú descargues. | ✅ Real (ARGOS no verifica su origen) |

Si pides un ticker real (p. ej. `AAPL`) sin tener datos reales, ARGOS **responde que no tiene datos**; nunca los inventa.

Para analizar AAPL con datos reales hoy mismo: descarga su histórico diario en CSV, guárdalo como `data/csv/AAPL.csv` (los CSV no se suben a git) y analízalo.

## Arquitectura

Ver **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: capas, cómo añadir proveedores, estrategias, backtesting y la futura integración con TradingView.

## Estado

- ✅ Capa de datos con proveedores intercambiables (demo + CSV), normalización y validación.
- ✅ Análisis técnico: medias, RSI, MACD, ATR, volumen, rentabilidades, soportes/resistencias.
- ✅ Motor de riesgo: volatilidad, caída máxima, VaR histórico y escenarios estadísticos.
- ✅ Conclusión auditable (factores visibles con peso y contribución) y explicación en lenguaje natural.
- ✅ Interfaz web oscura con paneles de activo, precio, indicadores, análisis, riesgo, conclusión y explicación.
- ✅ Estrategias de ejemplo (Buy & Hold, cruce de medias) y métricas de backtesting.
- ⏳ Motor de backtesting, análisis fundamental, noticias, paper trading, TradingView.
