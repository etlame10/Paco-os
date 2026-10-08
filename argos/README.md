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
| `csv` | Ficheros `data/csv/<TICKER>.csv` que tú descargues. | ✅ Real (ARGOS no verifica su origen). Los ficheros `DEMO-*.csv` se tratan como simulados. |

Si pides un ticker real (p. ej. `AAPL`) sin tener datos reales, ARGOS **responde que no tiene datos**; nunca los inventa.

**Formato exacto del CSV, con ejemplos: [docs/CSV_FORMAT.md](docs/CSV_FORMAT.md).** En resumen: `date,open,high,low,close,volume`, fechas `AAAA-MM-DD`, punto decimal, una fila por sesión (diario), fichero `data/csv/AAPL.csv`.

## Backtesting

Pestaña **Backtest** de la interfaz (o `GET /api/backtest?ticker=DEMO-LATERAL&strategy=sma_crossover`). Simula una estrategia sobre el histórico con capital, comisión, slippage y periodo configurables, y la compara **siempre** con Buy & Hold. Detalles, reglas y garantías anti look-ahead: **[docs/BACKTESTING.md](docs/BACKTESTING.md)**.

> Un backtest es un resultado histórico, no una predicción.

## Experimentos con datos reales

ARGOS trabaja con experimentos **pre-registrados**: hipótesis, reglas, activos, periodos y criterios se fijan antes de ver los datos (`protocols/`). Filosofía y registro: **[docs/EXPERIMENTOS.md](docs/EXPERIMENTOS.md)**. Qué datos aportar y cómo comprobarlos: **[docs/DATOS_REALES.md](docs/DATOS_REALES.md)**.

```bash
python -m argos.tools.tiingo descargar           # originales de Tiingo (necesita TIINGO_API_KEY)
python -m argos.tools.tiingo convertir           # CSV de ARGOS + control de integridad
python -m argos.data.check --protocolo EXP-001   # control de integridad de tus CSV
python -m argos.data.audit                       # auditoría profunda (calendario, ajustes, procedencia)
python -m argos.experiments.runner EXP-001       # experimento tal cual está registrado
```

## Arquitectura

Ver **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: capas, cómo añadir proveedores, estrategias, backtesting y la futura integración con TradingView.

## Estado

- ✅ Capa de datos con proveedores intercambiables (demo + CSV estricto), normalización y validación.
- ✅ Análisis técnico, motor de riesgo, conclusión auditable y explicación en lenguaje natural.
- ✅ Backtesting: motor independiente de la estrategia, comisión y slippage, comparación con Buy & Hold, auditoría anti look-ahead automática, interfaz con resumen, comparación, operaciones, gráfico y transparencia.
- ✅ Estrategia de prueba: cruce de medias 50/200 (sin optimizar).
- ✅ Control de integridad de datos, registro local de experimentos y ejecutor de experimentos pre-registrados (EXP-001, pendiente de datos reales).
- ⏳ Análisis fundamental, noticias, paper trading, TradingView.
