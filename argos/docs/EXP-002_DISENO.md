# EXP-002: diseño (fase 3)

> **Estado: BORRADOR pendiente de aprobación.** El protocolo propuesto está en
> [`borradores/EXP-002.json`](borradores/EXP-002.json). Todavía **no** está en `protocols/` ni en `LOCKS.json`, no se
> ha descargado ningún dato, no hay código nuevo y no se ha ejecutado nada. EXP-001 no se toca.
> Antecedentes y fuentes: [EXP-002_INVESTIGACION.md](EXP-002_INVESTIGACION.md).

## Decisiones ya tomadas por el usuario

- Estrategia: **GEM** (dual momentum de Antonacci). Es la única candidata; el filtro de 10 meses queda fuera.
- Capital inicial: **100**. Comisión: **1 por orden** (mínima fija).

## Decisiones tomadas por defecto en este borrador (pendientes de confirmar)

| Tema | Propuesta | Motivo |
| --- | --- | --- |
| Versión del filtro absoluto | El **S&P 500** frente a las letras del Tesoro (Petit, 2026). La variante con el filtro sobre el activo ganador queda como sensibilidad S1. | Las fuentes no coinciden. Las dos versiones solo difieren cuando VEU gana a SPY, VEU supera a las letras y SPY no: en ese caso esta versión va a bonos. **Antes de fijar el protocolo conviene comprobarlo en el libro.** |
| Activo fuera de EE. UU. | VEU | Un año más de historia que ACWX, lo que permite incluir la caída de 2008 en el tramo descriptivo. Su índice (FTSE) no es el del autor (MSCI). |
| Referencias pasivas | SPY comprar y mantener, y una 60/40 (30% SPY, 30% VEU, 40% AGG) **sin rebalanceo** | Con 100 de capital, rebalancear cada año costaría unos 3 al año (3 órdenes de 1). |
| Evaluación prospectiva | **No incluida** | La dejaste pendiente. Si se aprueba, sería un experimento propio. |
| Instrumentos | ETF de EE. UU. como sustituto de investigación | Un minorista de la UE compraría equivalentes UCITS. Queda documentado como limitación. |

## Reglas de GEM (inequívocas)

En la última sesión NYSE de cada mes, con cierres ajustados por dividendos y splits:

```
R(X) = P_aj(X, hoy) / P_aj(X, última sesión del mes, 12 meses antes) − 1

si R(SPY) ≤ R(BIL)       → AGG
si no, si R(SPY) ≥ R(VEU) → SPY
si no                     → VEU
```

- **Ejecución:** a la apertura de la sesión siguiente. Es más estricto que los backtests publicados, que ejecutan al cierre (esa variante es la sensibilidad S8).
- **Posición:** siempre un único activo al 100%. Si el objetivo cambia hay dos órdenes (venta total y compra total); si no cambia, ninguna.
- **Costes por orden:** `max(1, 0% × importe)`, más un deslizamiento del 0,05% sobre el precio.
- **Fracciones de participación:** se suponen permitidas. Es necesario con 100 de capital y queda documentado.

## Periodos

| Tramo | Fechas | Uso |
| --- | --- | --- |
| Previo a la publicación | 2008-07-01 → 2013-12-31 | Solo descriptivo. Se solapa con la muestra del autor (1974–2013). |
| **Evaluación** | **2014-01-01 → 2025-12-31** | **Criterios de éxito.** Es posterior al libro, pero **no es virgen**: ver limitaciones. |
| 2026 parcial | 2026-01-01 → 2026-09-30 | Solo descriptivo. Era la reserva de EXP-001 y ya ha transcurrido. |
| Reservado | desde 2026-10-01 | No se usa. |

Cada tramo empieza con 100 de capital. En la primera sesión se compra el objetivo de la última decisión anterior,
que solo usa datos previos. Así no hay el "arranque en liquidez hasta la primera señal" que distorsionó EXP-001.

## Criterios de éxito (periodo de evaluación, configuración principal)

- **C1. Caídas:** `MaxDD(GEM) ≤ 0,75 × MaxDD(SPY)`.
- **C2. Coste de la protección:** `CAGR neto(GEM) ≥ CAGR neto(60/40)`. Comparar solo con SPY sería injusto, porque
  GEM pasa tiempo en bonos. La 60/40 también reduce caídas; GEM tiene que aportar algo más que diversificar.

| Veredicto | Condición |
| --- | --- |
| **Mejora robusta** | C1 y C2 se cumplen; el IC 95% bootstrap de ΔCAGR(GEM − 60/40) queda entero por encima de 0; y C1 y C2 se siguen cumpliendo con costes ×2. |
| **Indicio no concluyente** | C1 y C2 se cumplen, pero falta alguna de las demás condiciones. |
| **No se ha demostrado mejora** | C1 o C2 no se cumplen. |
| **Inconcluso** | Datos bloqueados, menos de 132 decisiones mensuales válidas, fallo de la auditoría anti look-ahead o necesidad de desviarse del protocolo. |

Secundarias (se informan, no deciden): Sharpe y Sortino en exceso sobre BIL frente a SPY y frente a la 60/40,
CAGR frente a SPY, volatilidad, peor año natural, número de cambios, costes totales y tiempo en cada activo. También
se informa del comportamiento por régimen anual (alcista, bajista o lateral según SPY, igual que en EXP-001).

**Expectativa honesta, escrita antes de ver nada:** las replicaciones publicadas sugieren que GEM rindió menos que
el S&P 500 en este periodo, así que es probable que la rentabilidad frente a SPY no gane. La pregunta abierta es C2,
frente a la 60/40, con 3 de coste por cambio de activo.

## Sobreajuste y pruebas múltiples

- No se optimiza nada. Las reglas salen de la publicación y no de nuestros datos.
- **8 variantes de sensibilidad fijadas de antemano**: filtro sobre el ganador; ventanas de 6 y 9 meses; costes ×2;
  capitales de 50, 200 y 10.000; y ejecución al cierre. Se publican todas y **nunca** cambian el veredicto.
- Pruebas acumuladas en ARGOS: 8 de EXP-001 + 1 principal + 8 de sensibilidad = **17**. El número se publica junto
  al resultado.
- Incertidumbre: bootstrap por bloques de 12 meses sobre rendimientos mensuales emparejados, 10.000 réplicas,
  semilla fija.

## Limitaciones conocidas desde ya

1. **El periodo de evaluación no es independiente.** El mercado 2014–2025 es conocido, EXP-001 ya miró SPY y hay
   replicaciones de terceros sobre este mismo periodo. Es una **verificación con costes reales de capital bajo**,
   no un descubrimiento.
2. Unos 18 cambios de activo en el periodo de evaluación: muestra pequeña.
3. Se usan ETF de EE. UU. en dólares, sin tipo de cambio, sin impuestos y con fracciones de participación. Un
   inversor de la UE usaría ETF UCITS en euros.
4. VEU sigue un índice distinto del original del autor.
5. La versión del filtro absoluto no está verificada en el libro.

## Datos que hará falta descargar (solo tras registrar el protocolo)

SPY (ya descargado para EXP-001, pero el rango es más largo, hasta 2026-09-30), VEU, AGG y BIL. Se usa la cadena
existente sin cambios:

```
python -m argos.tools.tiingo descargar --protocolo EXP-002 --nueva-descarga
python -m argos.tools.tiingo convertir --protocolo EXP-002 --sobrescribir
python -m argos.data.audit --protocolo EXP-002 --salida auditoria_EXP-002.md
```

**Ojo:** `convertir --sobrescribir` reescribe `data/csv/SPY.csv`, que es el CSV que usa EXP-001. Antes de descargar
hay que decidir si se guarda una copia o se separan las carpetas. Lo resolvería en la fase 5, sin tocar los datos
de EXP-001.

## Implementación prevista (fase 5, tras registrar el protocolo)

- `argos/backtest/portfolio.py`: motor de pesos objetivo con varios activos, comisión mínima fija, ejecución en la
  apertura siguiente y calendario común estricto.
- `argos/strategy/gem.py`: señales mensuales que solo usan datos hasta el día de decisión, con auditoría por
  truncamiento.
- Métricas: Sharpe y Sortino en exceso sobre BIL, rendimientos mensuales y bootstrap por bloques.
- `argos/experiments/exp002.py`: ejecutor e informe propios. **`runner.py` de EXP-001 no se toca.**
- Tests con series sintéticas calculadas a mano, sin datos reales.

## Para aprobar

1. ¿Apruebas el borrador tal cual? (criterios C1 y C2, umbral de 0,75, periodos y referencias).
2. ¿Puedes comprobar en el libro qué se compara con las letras del Tesoro, el S&P 500 o el activo ganador?
   Si no se puede, se registra la versión del S&P 500 con esa limitación anotada.
3. Con tu aprobación: copio el borrador a `protocols/EXP-002.json`, añado su huella a `LOCKS.json` y lo subo
   (fase 4), **antes** de que descargues ningún dato.
