# Arquitectura de ARGOS

## Stack

- **Backend:** Python + FastAPI. Python es el ecosistema natural para análisis cuantitativo y backtesting (pandas, numpy).
- **Frontend:** HTML + CSS + JavaScript sin compilación, servido por el propio backend. El navegador solo habla con `/api/...`: **nunca** contiene claves; cualquier clave futura (proveedores de datos, IA) vivirá en variables de entorno del servidor.
- **Tests:** pytest (unitarios por capa + API + verificaciones de seguridad).

## Estructura

```
argos/
├── argos/
│   ├── core/            modelos compartidos (capas DATO/INDICADOR/INTERPRETACIÓN/CONCLUSIÓN) y salvaguardas
│   ├── data/            Data Layer: interfaz de proveedor, registro, normalización
│   │   └── providers/   demo (simulado), csv (datos reales locales) … futuros proveedores
│   ├── analysis/
│   │   ├── technical/   indicadores (funciones puras), soportes/resistencias, analizador con reglas
│   │   ├── fundamental/ interfaz preparada (sin implementar)
│   │   ├── news/        interfaz preparada (sin implementar)
│   │   └── synthesis.py interpretaciones → conclusión auditable
│   ├── risk/            volatilidad, drawdown, VaR, escenarios
│   ├── strategy/        contrato Strategy + señales hipotéticas + ejemplos
│   ├── backtest/        motor (solo señales), métricas, comparación, auditoría anti look-ahead, servicio
│   ├── explain/         capa de explicación (plantillas; futuro: LLM)
│   ├── pipeline.py      orquestador
│   └── api/app.py       API web (solo GET): /api/analyze, /api/backtest
├── web/                 interfaz
├── tests/
└── data/csv/            tus CSV con datos reales (ignorados por git)
```

## Flujo de un análisis

```
ticker → ProviderRegistry → MarketDataProvider → normalize_history
       → TechnicalAnalyzer (datos + indicadores + interpretaciones)
       → RiskEngine (métricas + interpretaciones + escenarios)
       → synthesize (factores visibles → conclusión)
       → Explainer (texto, solo reformula)
       → AnalysisReport (JSON) → interfaz
```

Cada `Interpretation` lleva la **regla** aplicada, los **ids de los indicadores** en que se basa y su **limitación**. La conclusión lista cada **factor** con su peso y contribución; la puntuación nunca se muestra sola. La procedencia de los datos (`Provenance.is_simulated`) viaja hasta la interfaz, que muestra un aviso y una etiqueta "DATOS DEMO" en cada panel.

## Cómo añadir un proveedor de datos

1. Crear `argos/data/providers/mi_proveedor.py` con una clase que herede de `MarketDataProvider` (`supports`, `get_asset_info`, `get_price_history`).
2. Devolver `PriceHistory` con una `Provenance` veraz (`is_simulated=False` solo si son datos de mercado reales).
3. Registrarlo en `default_registry()` (el orden define la prioridad).
4. Las claves de API se leen de variables de entorno en el servidor.

Nada más cambia: análisis, riesgo, interfaz y backtesting consumen la interfaz común.

## Cómo añadir una estrategia

```python
@register_strategy
class MiEstrategia(Strategy):
    name = "mi_estrategia"
    description = "…"
    def generate_signals(self, df):   # OHLCV hasta cada fecha
        return [Signal(date=..., action=SignalAction.ENTER_LONG, reason="…")]
```

Las señales son **hipotéticas**: las consume el backtesting (y en el futuro el paper trading). Regla anti-sesgo: la señal del día *t* solo usa datos hasta *t* y se ejecuta en *t+1* (hay un test que lo verifica para el cruce de medias). Los indicadores se reutilizan de `analysis/technical/indicators.py`, así que una estrategia calcula exactamente lo mismo que el análisis.

## Backtesting

Implementado. `DATOS → ESTRATEGIA → SEÑALES → BACKTESTER → RESULTADOS`: el `Backtester` (`backtest/engine.py`) solo recibe un DataFrame, una lista de señales y una configuración; no conoce la estrategia. `backtest/service.py` orquesta: carga los datos, genera las señales, audita que no haya look-ahead, simula estrategia y Buy & Hold con el mismo motor y compara. Ver **[BACKTESTING.md](BACKTESTING.md)**.

También servirá para **validar el propio ARGOS**: guardar cada análisis con su fecha y comprobar después si sus conclusiones acertaron más que el azar.

## Integración futura con TradingView

TradingView no ofrece una API pública de datos de mercado, así que su papel será otro:

1. **Visualización:** sustituir el gráfico SVG por la librería *Lightweight Charts* de TradingView (open source) o su widget, alimentados con los datos de nuestra API.
2. **Alertas como fuente de señales:** las alertas de TradingView pueden enviar *webhooks*. Se añadiría una ruta `POST /api/webhooks/tradingview` protegida con un secreto en el servidor, que convertiría cada alerta en una `Signal` hipotética para registrar y evaluar — nunca en una orden.
3. **Pine Script:** las estrategias que diseñes en TradingView se pueden reproducir como `Strategy` en ARGOS para backtestearlas con las mismas métricas.

## Seguridad

- `core/safety.py`: `LIVE_TRADING_ENABLED = False` (constante en código, no variable de entorno).
- No hay módulos de broker; los tests fallan si se importa una librería de broker o se define una función de órdenes.
- La API solo acepta GET; un test lo comprueba.
- Un test busca patrones de claves/secretos en `web/` y verifica que el frontend solo llama a `/api/`.
- Cabeceras de seguridad (CSP estricta, `nosniff`, `no-referrer`).
