# ARGOS_GoldTrend_H1: Expert Advisor para MetaTrader 5

> **Estado real:** código fuente escrito y revisado con **comprobaciones estáticas** (20 tests, ver abajo).
> **No se ha compilado:** en el entorno donde se escribió no hay MetaTrader 5 ni MetaEditor, y el proxy de red
> bloquea su descarga. **Tampoco se ha hecho ningún backtest.** No hay ningún resultado de rentabilidad, y una
> compilación correcta, cuando se haga, tampoco lo será.

## Relación con ARGOS

ARGOS (el sistema en Python) **no opera** y eso no cambia: `LIVE_TRADING_ENABLED` sigue en `False` y ningún
módulo Python importa librerías de broker. Este EA es un artefacto **separado**, en MQL5, que solo actúa dentro de
MetaTrader 5. Como salvaguarda adicional, que la especificación no pedía:

- **En el Strategy Tester siempre puede operar** (es un simulador).
- **Fuera del Tester no opera por defecto.** En una cuenta DEMO o de concurso exige `InpAllowDemoTrading = true`,
  y en una cuenta REAL, `InpAllowRealTrading = true`. Ambas vienen en `false`.

## Instalación y compilación

1. En MetaTrader 5: **Archivo → Abrir carpeta de datos**. Copia `ARGOS_GoldTrend_H1.mq5` a `MQL5/Experts/ARGOS/`.
2. Abre MetaEditor (**F4**), abre el fichero y pulsa **Compilar (F7)**.
3. En la pestaña **Errores** debe aparecer `0 errors, 0 warnings`. Si aparece alguno, **no lo uses**: copia el
   mensaje exacto para corregirlo. Este código no se ha compilado todavía.
4. En el terminal, **Navegador → Asesores expertos → Actualizar**. Aparecerá `ARGOS/ARGOS_GoldTrend_H1`.

El fichero está en UTF-8 con BOM y saltos de línea CRLF, para que MetaEditor muestre bien los acentos de los
mensajes.

## Reglas exactas

Se evalúan **una sola vez por vela H1 nueva**, siempre sobre la **última vela H1 cerrada** (índice 1), aunque el
gráfico esté en otra temporalidad.

| | Condición |
| --- | --- |
| **BUY** | `cierre[1] > EMA200[1]` y `RSI14[1] > 55` |
| **SELL** | `cierre[1] < EMA200[1]` y `RSI14[1] < 45` |
| Sin entrada | `45 ≤ RSI ≤ 55`, cierre igual a la EMA, o cualquier comprobación fallida |

- **SL:** 2 × ATR14[1] desde el precio previsto (Ask en compras, Bid en ventas), redondeado al tick **alejándose**
  de la entrada. **TP:** 2 × esa misma distancia (ratio 1:2).
- **Volumen:**
  - Riesgo objetivo = equidad × 0,5 %.
  - La pérdida por lote al llegar al SL se calcula con `OrderCalcProfit` y se contrasta con
    `SYMBOL_TRADE_TICK_VALUE_LOSS` / `SYMBOL_TRADE_TICK_SIZE`. Si difieren más de un 5 %, se usa la **mayor** y se
    registra.
  - A esa pérdida se suma `InpCommissionPerLot` (por defecto 0, porque la API no expone la comisión del bróker).
  - Lotes = riesgo / pérdida por lote, **redondeados hacia abajo** a `SYMBOL_VOLUME_STEP` y limitados por
    `SYMBOL_VOLUME_MAX` y `SYMBOL_VOLUME_LIMIT`.
  - Si el resultado queda por debajo de `SYMBOL_VOLUME_MIN`, **no se opera** y se registra el motivo.
- **Antes de enviar** se comprueba, en este orden:
  1. el entorno: Tester, demo o real, y permisos;
  2. las posiciones: aislamiento por símbolo y Magic Number;
  3. Bid y Ask válidos;
  4. el spread;
  5. que el símbolo admita la dirección de entrada;
  6. la distancia mínima de stops (`SYMBOL_TRADE_STOPS_LEVEL`);
  7. el volumen;
  8. el margen libre (`OrderCalcMargin`);
  9. `OrderCheck`.
- **Envío:** una orden a mercado con SL y TP, el `MagicNumber`, la desviación `InpMaxDeviationPoints` y el modo de
  llenado admitido por el símbolo (FOK, luego IOC y si no RETURN). **Un único intento por vela, sin reintentos.**
- **Deslizamiento:** si el precio real difiere del previsto, se recolocan SL y TP a la **misma distancia** desde el
  precio real, así que el riesgo por lote y el ratio 1:2 se conservan. Si el bróker no lo permite por distancia
  mínima o nivel de congelación, se mantienen los niveles enviados y se registra.
- **Sin** trailing, martingala, grid, promediado ni cierre por señal contraria. La posición se cierra por SL, por TP o
  por intervención externa.

### Spread en puntos

`MaxSpreadPoints = 35` se mide en **puntos del bróker** (`SYMBOL_POINT`): spread = (Ask − Bid) / `SYMBOL_POINT`.
**No son 35 centavos.** Si tu bróker cotiza XAUUSD con 2 decimales (punto 0,01), 35 puntos son 0,35 USD por onza.
Si cotiza con 3 decimales (punto 0,001), son 0,035 USD por onza. Consulta **Especificación del símbolo** y el
mensaje de inicio del EA, que registra el punto y los dígitos. El filtro solo bloquea **nuevas** entradas.

### Ejemplo aritmético de volumen (cifras HIPOTÉTICAS, no son las de ningún bróker)

| Dato | Valor hipotético |
| --- | --- |
| Equidad | 10.000 |
| Riesgo (0,5 %) | 50 |
| ATR14 | 12,00 |
| Distancia del SL (2 × ATR) | 24,00 |
| Pérdida por lote, si 1 lote = 100 oz | 24 × 100 = 2.400 |
| Lotes sin redondear | 50 / 2.400 = 0,0208 |
| Lotes con paso 0,01, hacia abajo | 0,02 → riesgo real 48 ≤ 50 |
| Si el volumen mínimo fuera 0,10 | 0,10 × 2.400 = 240 > 50 → **no se opera** |

El EA no usa estas cifras: lee siempre las especificaciones reales del símbolo de tu bróker.

### Magic Number y tipo de cuenta

- **Hedging:** solo cuentan las posiciones del símbolo con su `MagicNumber`. Si ya hay una, no se abre otra. Las
  operaciones manuales o de otros EA se ignoran y nunca se tocan.
- **Netting / exchange:** hay una sola posición neta por símbolo. Si existe una posición ajena (otro Magic Number o
  manual), o hay órdenes pendientes en el símbolo, **no se abre nada** y se registra "no se puede garantizar el
  aislamiento".
- El EA nunca cierra posiciones. Solo modifica el SL y el TP de **su** posición, tras comprobar el Magic Number.

### Símbolo y temporalidad

- Si el símbolo del gráfico no empieza por `InpExpectedSymbol` ("XAUUSD"; admite variantes como `XAUUSD.` o
  `XAUUSDm`) y `InpBlockOnSymbolMismatch = true`, el EA **no se inicia**.
- Si el gráfico no está en H1, se avisa, pero las señales se calculan igualmente con velas H1.

## Parámetros

| Parámetro | Por defecto | Nota |
| --- | --- | --- |
| `InpMagicNumber` | 20261010 | Cámbialo si usas varias instancias |
| `InpEmaPeriod` / `InpRsiPeriod` / `InpAtrPeriod` | 200 / 14 / 14 | |
| `InpRsiBuyLevel` / `InpRsiSellLevel` | 55 / 45 | Comparaciones estrictas (> y <) |
| `InpMinHistoryBars` | 600 | Calentamiento de la EMA200 (3 × 200) |
| `InpRiskPercent` | 0,5 | Se rechaza fuera de (0, 5] |
| `InpSlAtrMultiplier` / `InpRewardRiskRatio` | 2 / 2 | |
| `InpCommissionPerLot` | 0 | Comisión ida y vuelta por lote, sumada al riesgo |
| `InpMaxSpreadPoints` | 35 | Puntos del bróker |
| `InpMaxDeviationPoints` | 20 | Desviación aceptada al ejecutar |
| `InpLogEveryBar` | false | Registrar también las velas sin señal |
| `InpAllowDemoTrading` / `InpAllowRealTrading` | false / false | Fuera del Tester |

## Pruebas realizadas (resultados reales)

| Prueba | Resultado |
| --- | --- |
| Compilación en MetaEditor | **NO REALIZADA**: MetaTrader 5 no está disponible en el entorno y su descarga está bloqueada. |
| `argos/tests/test_mt5_ea_static.py` (estática, Python) | **20 passed**. Comprueba: llaves y paréntesis equilibrados; ausencia de funciones MQL4; los 11 valores por defecto de la especificación; indicadores mediante handles en H1, liberados y leídos solo de la vela 1; regla de señal exacta; una evaluación por vela y sin bucles alrededor de `OrderSend`; Magic Number en todas las peticiones y `OrderCheck`; límites de volumen, stops, margen, spread y llenado; aislamiento en netting y hedging; nunca se cierran posiciones; permiso expreso fuera del Tester. |
| Comprobación de mutaciones de las pruebas estáticas | Se alteró el código en memoria de seis formas (leer la vela en curso, `>=` en el RSI, sin Magic Number, una llave de más, un bucle de reintento, riesgo del 1 %) y cada alteración la detectó al menos una prueba. |
| Backtest, modo visual, ticks reales | **NO REALIZADOS.** |

Las pruebas estáticas **no** sustituyen a la compilación ni demuestran que el EA funcione en MetaTrader.

## Plan de pruebas pendiente (en tu MetaTrader 5)

1. **Compilación:** F7 → `0 errors, 0 warnings`. Pásame cualquier mensaje.
2. **Inicio:** adjuntar el EA a XAUUSD H1 en una cuenta DEMO **sin** activar `InpAllowDemoTrading`. En la pestaña
   **Expertos** debe aparecer el mensaje de inicio (Magic, cuenta, modo, punto, dígitos) y, con una señal,
   "NO ejecutada: cuenta DEMO/CONCURSO y InpAllowDemoTrading = false".
3. **Modo visual del Tester** (Ctrl+R, «Visualización»):
   - las entradas solo ocurren al abrir una vela H1 nueva;
   - el cierre de la vela anterior está del lado correcto de la EMA200, con el RSI por encima de 55 o por debajo
     de 45;
   - SL = 2 × ATR, TP = 2 × SL;
   - nunca hay dos posiciones a la vez.
4. **Contabilidad:** para 3–5 operaciones, recalcular a mano lotes, riesgo, SL y TP con la especificación del
   símbolo y el registro del EA. Comprobar en **Historial** el Magic Number.
5. **Casos límite en el Tester:**
   - `InpMaxSpreadPoints = 1`: no debe abrir y debe registrar el spread;
   - `InpRiskPercent` muy bajo: "el volumen mínimo supera el riesgo";
   - depósito mínimo: "margen insuficiente";
   - otro símbolo: el EA no se inicia.
6. **Backtest con «Cada tick basado en ticks reales»**, si tu bróker los ofrece. Configura la comisión real del
   bróker en el Tester y en `InpCommissionPerLot`. Anota el spread (real o fijo) y el retraso de ejecución.
7. **Separación desarrollo / fuera de muestra**, siguiendo el método de ARGOS. Propuesta, **pendiente de tu
   decisión**: registrar antes un protocolo (p. ej. EXP-003) con las reglas tal y como están, un periodo de
   desarrollo y otro posterior que **no se mire** hasta el final, y criterios de éxito fijados antes de ver nada.
8. **Métricas** (informe del Tester más cálculo propio): beneficio neto, factor de beneficio, máxima caída (absoluta
   y relativa), número de operaciones, esperanza matemática por operación, CAGR (con fechas inicial y final) y
   exposición (tiempo en mercado).
9. **Sensibilidad:** pocas variantes razonables fijadas antes (p. ej. multiplicador de SL 1,5/2/2,5 y niveles RSI
   ±2). Se publican todas y **nunca se elige la mejor** como resultado.
10. **Registro de cada prueba:** versión del EA, bróker y servidor, símbolo exacto y su especificación (punto,
    dígitos, contrato, volúmenes), periodo, modelo de ticks, spread, comisión, depósito, apalancamiento y
    parámetros.

## Limitaciones conocidas

- **No compilado.** Puede haber errores o avisos que solo MetaEditor detecta. Las comprobaciones estáticas no los
  cubren.
- **Brókeres con ejecución "Market" que no aceptan SL y TP en la orden de apertura:** la orden se rechaza y se
  registra. El EA **no** abre sin stops para ponerlos después, porque dejaría la posición sin protección.
- **Comisiones y swaps:** MQL5 no expone la comisión del bróker. Solo se suma al riesgo si la indicas en
  `InpCommissionPerLot`. Los swaps no se incluyen en el riesgo.
- **Huecos de precio:** con huecos (fines de semana, noticias) la pérdida real puede superar la del SL.
- **Primera vela:** al iniciar el EA no se evalúa la vela en curso; la primera evaluación es en la siguiente vela H1.
- **Datos no listos:** si al abrir una vela los indicadores no están calculados, se reintenta solo la **lectura** en
  el tick siguiente. No hay ninguna orden en juego, así que no puede duplicar operaciones.
- **Llenado parcial** (`DONE_PARTIAL`): se acepta el volumen ejecutado, con riesgo menor que el objetivo.
- **Coincidencia de símbolo por prefijo:** un símbolo distinto que empiece por "XAUUSD" se aceptaría.
- No hay ningún dato sobre si esta estrategia gana o pierde dinero.
