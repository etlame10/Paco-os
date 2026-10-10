# Backtesting en ARGOS

> **Un backtest es un RESULTADO HISTÓRICO, no una PREDICCIÓN.** Describe qué habría pasado en el pasado con unas reglas y unos supuestos concretos. Los resultados históricos no garantizan resultados futuros.

## Flujo

```
DATOS ──► ESTRATEGIA ──► SEÑALES ──► BACKTESTER ──► RESULTADOS
(CSV/demo)  (reglas)     (fecha +     (simula la     (métricas + comparación
                          acción)      cuenta)         con Buy & Hold)
```

| Pieza | Archivo | Sabe de… | No sabe de… |
| --- | --- | --- | --- |
| Estrategia | `argos/strategy/` | precios hasta cada fecha | costes, capital, ejecución |
| Backtester | `argos/backtest/engine.py` | fechas, precios, señales, costes | qué estrategia generó las señales |
| Métricas | `argos/backtest/metrics.py` | la curva de capital y las operaciones | — |
| Comparación | `argos/backtest/comparison.py` | métricas de ambas | — |
| Orquestación | `argos/backtest/service.py` | todo lo anterior | — |

## Reglas de simulación

- **Solo largos**: comprado o en liquidez. Sin cortos ni apalancamiento.
- **Tamaño**: todo el efectivo disponible en cada compra (se admiten fracciones de acción).
- **Ejecución**: la señal se calcula con el **cierre** de la sesión *t* y se ejecuta en la **apertura** de *t+1*. Una señal de la última sesión no se ejecuta.
- **Compra**: precio = apertura × (1 + slippage); cantidad = efectivo / (precio × (1 + comisión)).
- **Venta**: precio = apertura × (1 − slippage); efectivo = cantidad × precio × (1 − comisión).
- **Capital diario** = efectivo + cantidad × cierre.
- **Final del periodo**: la posición abierta se vende al cierre de la última sesión, pagando costes (igual para la estrategia y para Buy & Hold).
- **Señales redundantes** (comprar estando comprado, vender sin posición) se ignoran y se listan.
- **Buy & Hold**: mismo motor, mismo periodo, mismos costes; compra en la apertura de la 2.ª sesión.

## Garantías contra el look-ahead bias

1. **Indicadores**: tests que comprueban que el valor de SMA, EMA, RSI, MACD y ATR en *t* es idéntico con o sin datos posteriores a *t*.
2. **Estrategia**: en cada backtest se ejecuta una **auditoría automática**: se recalculan las señales cortando los datos en varias fechas (incluidas las de cada señal) y deben coincidir con las del histórico completo. Si no coinciden, el backtest se **rechaza**. Hay un test con una estrategia tramposa que comprueba que se detecta.
3. **Periodo**: la estrategia nunca recibe datos posteriores a la fecha de fin elegida. Sí puede usar datos *anteriores* al inicio para calentar indicadores (eso no es información futura).
4. **Motor**: rechaza ejecutar una operación el mismo día o antes que su señal (comprobación explícita en código y en tests).

## Métricas

| Métrica | Definición |
| --- | --- |
| Rentabilidad total | capital final / capital inicial − 1 |
| Rentabilidad anualizada | (final/inicial)^(365,25 / días naturales) − 1. No se da si el periodo es inferior a 1 año. |
| Caída máxima | mayor caída de la curva de capital desde un máximo previo |
| Volatilidad | desviación típica de los rendimientos diarios del capital × √252 (mín. 60 sesiones) |
| Sharpe | media / desviación de los rendimientos diarios × √252, con tasa libre de riesgo 0 % (mín. 60 sesiones) |
| Win rate | operaciones con resultado neto > 0 / operaciones cerradas |
| Beneficio medio, mejor, peor | sobre el resultado neto de cada operación (con costes) |
| Tiempo invertido | % de sesiones con posición abierta al cierre |

## Cómo leer la comparación

ARGOS no considera buena una estrategia por ganar dinero. Pregunta: **¿mejoró a mantener el activo?** Compara rentabilidad, caída máxima, volatilidad y Sharpe, y añade advertencias:

- Menos de **30 operaciones** → no hay base estadística.
- Un solo activo y un solo periodo → hay que repetir en otros.
- Datos simulados → solo valida el motor, no dice nada del mercado.

## Primera estrategia: cruce de medias 50/200

Parámetros por defecto **fijados de antemano, sin optimizar**: son las mismas medias que ya usa el análisis técnico de ARGOS (regla "SMA50 > SMA200 → estructura alcista"), así que el backtest pone a prueba una regla que ARGOS ya utiliza. Se pueden cambiar a mano, pero **no se buscan "los mejores parámetros"**: probar cientos de combinaciones y quedarse con la mejor produce sobreajuste (overfitting).

Limitación conocida: con 50/200 hay pocos cruces, así que hace falta un histórico largo (varios años) para tener un número de operaciones con algún valor estadístico.

## Limitaciones actuales

- Una sola posición, solo largos, todo el capital.
- Sin dividendos, impuestos, intereses del efectivo, ni límites de liquidez.
- Comisión proporcional (sin mínimo fijo por operación).
- Un activo por backtest (sin carteras).
- Solo datos diarios.
