# Datos reales para el experimento EXP-001

ARGOS **no descarga datos**. Tú los consigues de una fuente fiable, los dejas en `data/csv/` y ARGOS los comprueba antes de usarlos. Si algo no cuadra, avisa o se niega a continuar; nunca rellena ni corrige.

## 1. Qué histórico necesitamos (explicado sencillo)

Para cada activo, una tabla con **una fila por día de mercado** desde **enero de 2007** hasta **el 31 de diciembre de 2025**. Cada fila tiene el precio de apertura, el máximo, el mínimo, el cierre y el volumen de ese día.

- **¿Por qué desde 2007?** Las reglas se evalúan desde 2008, pero la media de 200 sesiones necesita casi un año de datos previos para poder calcularse.
- **¿Por qué hasta 2025?** Es el final del periodo fuera de muestra. 2026 queda reservado para una validación futura y **no se mira**.
- **Precios ajustados.** Si la acción tuvo un *split* o repartió dividendos, los precios antiguos deben estar ajustados. Si no lo están, ARGOS vería una "caída" falsa el día del split y la contaría como pérdida.

## 2. Formato exacto

Fichero `data/csv/<TICKER>.csv` (por ejemplo `data/csv/SPY.csv`):

```csv
date,open,high,low,close,volume
2007-01-03,...,...,...,...,...
2007-01-04,...,...,...,...,...
```

- Fechas `AAAA-MM-DD`. Punto decimal y sin separador de miles. Coma entre campos.
- Solo datos **diarios**. El volumen es obligatorio; si la fuente no lo tiene, pon `0`.
- Las columnas extra se ignoran. Todos los detalles están en [CSV_FORMAT.md](CSV_FORMAT.md).

**Procedencia (muy recomendable):** junto a cada CSV, crea `data/csv/<TICKER>.source.txt` con una línea que diga de dónde salió. Por ejemplo: `Descarga manual desde <fuente>, 2026-10-08, precios ajustados por splits y dividendos`. Aparecerá en el informe; si falta, el informe lo marca como "no documentada".

### Si tu fuente da `Adj Close`

Muchas descargas traen `Open, High, Low, Close, Adj Close, Volume`. En ellas `Close` suele estar ajustado por splits pero **no** por dividendos, y `Adj Close` sí lo está por ambos. Para que las cuatro columnas queden en la misma escala ajustada:

```bash
python -m argos.tools.adjust_csv descarga_KO.csv data/csv/KO.csv
```

Multiplica apertura, máximo y mínimo por `Adj Close / Close`, usa `Adj Close` como cierre y lo anota en `KO.source.txt`. No rellena nada: si una fila está incompleta (por ejemplo `null`), se detiene e indica la línea.

## 3. Qué activos y por qué

| Ticker | Papel | Por qué |
| --- | --- | --- |
| **SPY** | Índice amplio | ETF del S&P 500. Usamos el ETF porque el índice en sí no se puede comprar y no incluye dividendos. |
| **KO** | Empresa grande y estable | Coca-Cola: defensiva y poco volátil. Un caso donde una regla de tendencia puede ir peor. |
| **AAPL** | Tecnológica | Apple. ⚠ **Sesgo de supervivencia**: la elegimos sabiendo que le fue muy bien. Su resultado sobrevalora lo que se habría podido esperar en 2008. |
| **XOM** | Comportamiento distinto | ExxonMobil: cíclica ligada al petróleo, con una larga fase bajista entre 2014 y 2020. Aporta régimen bajista y lateral. |
| GLD *(complementario)* | Oro | No es una acción: permite ver la regla en otro tipo de mercado. |
| EFA *(complementario)* | Acciones fuera de EE. UU. | Mercados desarrollados no estadounidenses, con 2008-2025 mucho más lateral que el S&P 500. |

Los cuatro primeros cumplen tu propuesta y deciden los criterios. Los dos complementarios **no cuentan para los criterios**; amplían la muestra con mercados distintos y ayudan a no sacar conclusiones de un único tipo de activo. Si solo consigues los cuatro principales, el experimento es válido igualmente.

**Por qué no más activos (todavía):** con 4 activos y 2 periodos solo hay 8 observaciones, y además no son independientes (2008, 2020 y 2022 afectaron a todos a la vez). Es suficiente para una primera prueba honesta, pero no para concluir nada general. Ampliar la muestra será, en su caso, un experimento nuevo con su propio protocolo.

## 4. Periodos

| Periodo | Fechas | Para qué |
| --- | --- | --- |
| Calentamiento | 2007 | Solo para que las medias de 50 y 200 sesiones puedan calcularse. No se evalúa. |
| **Desarrollo** | 2008-01-01 → 2016-12-31 | Crisis de 2008 y mercado alcista posterior. |
| **Fuera de muestra** | 2017-01-01 → 2025-12-31 | 2018, la caída de 2020 y el mercado bajista de 2022. **Aquí se evalúan los criterios.** |
| Reservado | 2026 → | No se mira. Queda para una validación futura. |

Mínimo: los datos deben empezar como muy tarde el 11 de enero de 2007 (10 días de tolerancia) y llegar hasta el 31 de diciembre de 2025. Un activo que no cubra el periodo queda **excluido** y se indica así en el informe, sin recortar el periodo para que encaje.

## 5. Cómo comprobar que los datos son válidos

```bash
python -m argos.data.check --protocolo EXP-001
```

Para cada activo comprueba lo siguiente, sin modificar nada:

| Comprobación | Aviso | Bloqueo |
| --- | --- | --- |
| Fechas | — | fechas futuras o inválidas |
| Duplicados | — | una fecha repetida |
| Frecuencia | — | no es diaria |
| Huecos | > 7 días naturales sin datos | > 20 días |
| Sesiones por año | < 240 sesiones en un año completo | — |
| Precios imposibles | — | algún precio ≤ 0 |
| Coherencia OHLC | alguna sesión con máximo < cierre, etc. | más del 1 % de sesiones |
| Rango diario | máximo/mínimo > 50 % en un día | — |
| Volumen | todo 0, o > 5 % de días a 0 | volumen negativo |
| Precios congelados | 5+ sesiones idénticas seguidas | — |
| Splits | — | salto con proporción de split (2:1, 3:1, 1:10…) |
| Saltos | variación diaria > 40 % sin proporción de split | — |
| Longitud | — | no cubre 2007-01 → 2025-12 o < 10 años |

Un **bloqueo** excluye el activo del experimento. Un **aviso** no lo excluye, pero aparece en el informe para que lo revises. ARGOS no puede verificar el ajuste por dividendos: eso depende de tu fuente.

## 6. Ejecutar el experimento

```bash
python -m argos.data.check --protocolo EXP-001     # 1. comprobar los datos
python -m argos.experiments.runner EXP-001         # 2. ejecutar el experimento tal cual
```

El informe se guarda en `data/experiments/results/EXP-001/<fecha>/report.md` (y `results.json`). Cada backtest queda en el registro `data/experiments/registry.jsonl`.

Para ver el procedimiento funcionando sin datos reales:

```bash
python -m argos.experiments.runner EXP-001 --ensayo-demo
```

Usa series **simuladas**, marcadas como tales en todo el informe. No es el experimento.
