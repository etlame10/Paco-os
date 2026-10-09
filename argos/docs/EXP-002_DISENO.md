# EXP-002: diseño (fase 3, borrador final v3)

> **Estado: BORRADOR v3 (final propuesto), pendiente de autorización explícita.** Protocolo propuesto:
> [`borradores/EXP-002.json`](borradores/EXP-002.json). **No** está en `protocols/` ni en `LOCKS.json`. No se ha
> descargado ningún dato, no hay código nuevo, no se ha ejecutado EXP-002 y EXP-001 no se ha tocado.
> Antecedentes y fuentes: [EXP-002_INVESTIGACION.md](EXP-002_INVESTIGACION.md).

Leyenda: **[CONFIRMADO]** = visto en una fuente del autor (aunque sea a través de extractos de búsqueda);
**[PENDIENTE]** = interpretación no verificada en el libro; **[DECISIÓN]** = elección de diseño nuestra.

## Cambios de la v3 respecto a la v2

| # | Cambio |
| --- | --- |
| 1 | Moneda: queda explícito que 100 USD **no** representan una inversión de 100 EUR y que las variantes de capital o de costes **no** equivalen a modelar el tipo de cambio (§2). |
| 2 | C2 usa el CAGR neto de costes, con su justificación (§5). |
| 3 | MaxDD: fórmula completa, fechas incluidas y momento en que cada coste entra en la curva (§5). |
| 4 | Contabilidad de costes con una comprobación sintética: cada coste se cuenta una sola vez en las tres carteras (§3). |
| 5 | El umbral del 0,75 se declara **exploratorio** (§5). |
| 6 | La regla principal y S1 se presentan con la fuente de cada una (§1). |
| 7 | Las 132 fechas mensuales son fechas de **decisión**, no operaciones, y se añade una comprobación explícita (§4). |

## Cambios de la v2 respecto a la v1

| # | Cambio | Motivo |
| --- | --- | --- |
| 1 | La fuente de la regla pasa de "Petit" a "web del autor, vía extractos", y se separa lo confirmado de lo pendiente (§1). | Punto 1 de la revisión. |
| 2 | La moneda queda fijada en **USD** (100 USD de capital y 1 USD por orden). | Antes era ambiguo. |
| 3 | Fórmulas exactas de cada orden, número de órdenes y coste total, incluido el escenario de costes ×2. | Punto 3. |
| 4 | La evaluación empieza el **2015-01-01** (antes, 2014-01-01). | El libro salió en octubre de 2014; 2014 no era posterior a la publicación. |
| 5 | Fórmulas de C1, C2, MaxDD, CAGR, Sharpe y Sortino. | Punto 5. |
| 6 | La 60/40 pasa a llamarse 30/30/40 y se define con cantidades fijas y pesos que evolucionan solos. | Punto 6. |
| 7 | Los datos de EXP-002 se guardarán en carpetas propias. | Punto 9: con v1, la conversión habría sobrescrito `data/csv/SPY.csv` de EXP-001. |

## 1. La regla de GEM: qué está confirmado y qué no

No he podido leer el libro ni los PDF. Desde este entorno no se puede abrir SSRN, optimalmomentum.com, medium.com
ni webs de reseñas. Lo siguiente sale de **extractos de búsqueda**, no de la lectura completa de las páginas.

| Elemento | Estado | Fuente |
| --- | --- | --- |
| Primero se mira la **tendencia del S&P 500**; si es bajista, bonos | **[CONFIRMADO]** (extracto) | optimalmomentum.com, páginas sobre GEM: [Extended Backtest](https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/), [FAQ](https://www.optimalmomentum.com/faq/) |
| Si es alcista, se elige S&P 500 o MSCI ACWI ex-US por su rentabilidad de 12 meses | **[CONFIRMADO]** (extracto) | ídem |
| Ventana de 12 meses en ambos pasos y rebalanceo mensual | **[CONFIRMADO]** (extracto) | ídem |
| Refugio: bonos agregados de EE. UU. | **[CONFIRMADO]** (extracto) | ídem, y reseñas del libro |
| GEM se creó en 2013; libro publicado en **octubre de 2014** | **[CONFIRMADO]** | Autor (extracto); fichas de [OverDrive](https://nlb.overdrive.com/media/1991203) (9 oct. 2014) y [Amazon](https://us.amazon.com/Dual-Momentum-Investing-Innovative-Strategy/dp/0071849440) (10 oct. 2014) |
| "Tendencia alcista" = rentabilidad de 12 meses **mayor que la de las letras del Tesoro** (no mayor que 0) | **[PENDIENTE]** | Lo apoyan el resumen del artículo SSRN 2042750 (umbral de letras, aunque en otro modelo) y Petit (2026). No verificado en el libro. |
| Índices exactos de bonos y letras del libro y día del mes del cálculo | **[PENDIENTE]** | — |
| Variante con el filtro sobre el activo **ganador** | Discrepancia de fuentes secundarias | Portfolio123, strategyindex.io y otras. Queda como **variante S1**, nunca como sustituto. |

| | Regla | Fuente | Estado |
| --- | --- | --- | --- |
| **Principal** | Bonos si R(SPY) ≤ R(BIL); si no, el mayor de R(SPY) y R(VEU) | Extractos de optimalmomentum.com (orden: S&P 500 primero) y Petit 2026, SSRN 7427878 (resumen de un preprint sin revisión por pares) | **No verificada en el libro.** La incertidumbre se mantiene hasta poder comprobarla. |
| **S1** | Bonos si max(R(SPY), R(VEU)) ≤ R(BIL) | Foro de Portfolio123, strategyindex.io y otras fuentes secundarias, ninguna del autor | Solo sensibilidad. |

Las dos versiones solo difieren en un caso: VEU gana a SPY, VEU supera a las letras y SPY no. Entonces la versión
del autor va a bonos y S1 se queda en VEU.

**Recomendación:** antes de autorizar, que alguien con el libro compruebe la página donde se describe GEM. Si no es
posible, se registra tal cual, con la limitación anotada en `source_status`. Si una verificación posterior mostrara que
el libro usa la regla de S1, **EXP-002 no se cambia**: se documenta la desviación y, si procede, se registra EXP-003.

## 2. Moneda y capital **[DECISIÓN]**

- El experimento principal trabaja en **USD**, la moneda de los precios: capital C0 = **100 USD** y comisión
  m = **1 USD por orden**.
- **No representa exactamente una inversión de 100 EUR.** No se modela el tipo de cambio EUR/USD. Para un inversor en
  euros, todas las carteras quedarían multiplicadas por un tipo de cambio que varía cada día. Eso no cambia qué activo
  elige GEM, pero sí la curva de capital, la profundidad de las caídas medidas en euros y el peso relativo de una
  comisión fija en euros.
- Las variantes de capital (S5, S6 y S7) y de costes (S4) miden la sensibilidad al tamaño de la cuenta y al coste.
  **No equivalen a modelar el tipo de cambio** ni lo sustituyen. Modelarlo exigiría otra serie de datos y otro
  experimento.
- Es solo un backtest: no hay órdenes reales ni conexión con ningún broker.

## 3. Costes: fórmulas, órdenes y coste total

Precios: Pa = apertura ajustada, Pc = cierre ajustado. m = 1 y s = 0,0005 en la configuración principal.

| Operación | Fórmula |
| --- | --- |
| Comisión por orden | c = max(m, 0 × importe) = m |
| Compra | cantidad = (efectivo asignado − c) / (Pa × (1 + s)) |
| Venta | ingreso = cantidad × Pa × (1 − s) − c |
| Liquidación final | ingreso = cantidad × Pc × (1 − s) − c por cada posición, al cierre de la última sesión |
| Deslizamiento registrado | cantidad × P × s en cada orden |
| Coste total | Σ comisiones + Σ deslizamiento |

| Cartera | Órdenes | Comisión total (m = 1) | Costes ×2 (m = 2, s = 0,10%) |
| --- | --- | --- | --- |
| GEM | 1 + 2K + 1 | 2 + 2K | 4 + 4K |
| SPY comprar y mantener | 2 | 2 | 4 |
| 30/30/40 sin rebalanceo | 3 + 3 | 6 | 12 |

K es el número de cambios de activo. **Es aritmética, no un resultado:** con K ≈ 16, el ≈1,5 al año publicado
durante 11 años, GEM pagaría ≈34 USD de comisiones sobre 100 de capital, frente a 6 de la 30/30/40. Es decir, GEM
tendría que ganar en bruto del orden de 2–3 puntos al año más para empatar en C2. Con costes ×2, el doble. Es la
razón principal por la que C2 es exigente.

Si el efectivo disponible para una compra es ≤ c, el experimento se detiene y se declara inconcluso.

**Compras de varios activos a la vez** (solo en la 30/30/40): presupuesto = efectivo − n·m, siendo n el número de
compras. Cada activo recibe peso × presupuesto, y cantidad = peso × presupuesto / (Pa·(1 + s)).

**Contabilidad: cada coste se cuenta una sola vez.**

| Momento | GEM | SPY | 30/30/40 |
| --- | --- | --- | --- |
| Entrada (primera apertura del tramo) | 1 compra | 1 compra | 3 compras |
| Decisión mensual sin cambio de objetivo | 0 órdenes | — | — |
| Cambio de activo (apertura siguiente a la decisión) | 1 venta + 1 compra | — | — |
| Liquidación final (cierre de la última sesión) | 1 venta | 1 venta | 3 ventas |
| **Total de órdenes** | **2 + 2K** | **2** | **6** |

- Cada orden paga exactamente **una** comisión m y **un** deslizamiento cantidad·P·s.
- Debe cuadrar la identidad V_T = C0 + Σ resultado bruto de mercado − Σ comisiones − Σ deslizamientos.
- Cada tramo se simula por separado, así que los costes de un tramo no pasan a otro.
- Las decisiones cuya ejecución caería después de la última sesión no generan órdenes. En el periodo de evaluación, la
  última decisión ejecutada es la del 2025-11-28, que se ejecuta el 2025-12-01. La del 2025-12-31 no se ejecuta.

**Comprobación sintética realizada** (precios inventados, no es el backtest): una implementación mínima de estas
fórmulas sobre 60 sesiones aleatorias da 8 órdenes para GEM con K = 3 y 5 decisiones con objetivo, 2 para SPY y 6
para la 30/30/40. La comisión total es igual al número de órdenes y la identidad de V_T cuadra con un error menor que
10⁻¹³ en las tres carteras. Esa comprobación se convertirá en un test permanente en la fase 5.

## 4. Fechas, señales, ejecución, dividendos y calendario

- **Evaluación: 2015-01-01 → 2025-12-31** **[DECISIÓN]**. Es el primer año natural completo tras la publicación del
  libro (octubre de 2014), así que no se elige una fecha de corte a la vista de nada. Hay **132 decisiones**: de
  2014-12-31 a 2025-11-28, comprobado con el calendario NYSE de ARGOS. La primera ejecución es el 2015-01-02.
- **Las 132 son fechas de decisión, no operaciones.** En cada una se calcula el objetivo, pero solo hay órdenes si
  cambia. El informe dará por separado el número de decisiones (debe ser 132), el número de cambios K
  (0 ≤ K ≤ 132) y el de órdenes de GEM (2 + 2K). Si no cuadran, el experimento es inconcluso.
- Tramos solo descriptivos: 2008-07-01 → 2014-12-31 (primera decisión el 2008-06-30) y 2026-01-01 → 2026-09-30.
- **Señal:** al cierre ajustado de la última sesión válida del mes. Se compara con el cierre de la última sesión
  válida del mismo mes un año antes. Una sesión es válida si está en el calendario NYSE y los cuatro activos tienen
  barra.
- **Ejecución:** apertura ajustada de la sesión válida siguiente. Una decisión cuya ejecución caería fuera del
  periodo no se ejecuta.
- **Dividendos:** precios `adj*` de Tiingo. El dividendo se reinvierte implícitamente en la fecha ex y sin comisión,
  como en un fondo de acumulación. Señales, ejecución y valoración usan los mismos precios.
- **Calendario:** si falta una sesión NYSE esperada en algún activo, se detiene. Nunca se rellena.
- **Inicio de cada tramo:** con capital en efectivo, comprando en la primera apertura el objetivo de la última
  decisión anterior. No hay arranque en liquidez como en EXP-001.

## 5. Criterios de éxito (idénticos para GEM y referencias)

**Puntos de la curva** (los mismos para las tres carteras):

- t = 0: V_0 = C0, efectivo justo antes de la primera apertura del tramo.
- t = 1 … T−1: cierre de cada sesión válida, **después** de las ejecuciones de esa apertura:
  V_t = efectivo_t + Σ_i cantidad_i · Pc_i(t). Las comisiones y el deslizamiento de esas órdenes ya se han
  descontado del efectivo.
- t = T: última sesión válida del tramo; V_T es el efectivo tras liquidar al cierre con costes.
- No se valoran aperturas ni precios intradía.

```
Pico_t = max(V_0, …, V_t)
DD_t   = 1 − V_t / Pico_t                        (DD_0 = 0)
MaxDD  = max(DD_0, …, DD_T)                      (fracción positiva)
CAGR   = (V_T / C0)^(365,25 / D) − 1             (D = días naturales entre la primera y la última sesión)

C1:  MaxDD(GEM) ≤ 0,75 · MaxDD(SPY comprar y mantener)
C2:  CAGR(GEM)  ≥ CAGR(30/30/40)
```

Mismo motor, mismas sesiones, mismos precios, mismos costes y mismas métricas para las tres carteras. Solo cambian
los pesos objetivo. Se compara sin redondear.

- **Por qué el CAGR neto en C2:** mide cuánto crece el capital después de pagar todo y es comparable entre carteras
  con distinto número de órdenes. La rentabilidad total dependería de la longitud del tramo, y el Sharpe ya es una
  métrica secundaria.
- **El umbral 0,75 de C1 es exploratorio.** Se eligió antes de calcular nada, pero conociendo a grandes rasgos el
  periodo (caídas del S&P 500 en 2020 y 2022, y bonos a la baja en 2022). **No es un umbral independiente ni
  validado estadísticamente.** El informe dará siempre la razón MaxDD(GEM)/MaxDD(SPY) exacta, además de si cumple o
  no el 0,75.

| Veredicto | Condición |
| --- | --- |
| Mejora robusta | C1 y C2; IC 95% de ΔCAGR(GEM − 30/30/40) entero por encima de 0; y C1 y C2 también con costes ×2 (S4) |
| Indicio no concluyente | C1 y C2, sin el resto |
| No se ha demostrado mejora | Falla C1 o C2 |
| Inconcluso | Datos bloqueados, sesión ausente, número de decisiones distinto de 132 o contabilidad que no cuadra, fallo de la auditoría anti look-ahead, falta de efectivo o necesidad de desviarse del protocolo |

**Secundarias** (se informan, no deciden): Sharpe en exceso sobre BIL, calculado como media(e)/desv(e)·√252 con
e_t = r_t − r_BIL,t; Sortino con la semidesviación de e; CAGR frente a SPY; volatilidad; peor año; K; costes; tiempo
en cada activo; regímenes anuales según SPY.

**Incertidumbre:** bootstrap circular por bloques de 12 meses sobre los rendimientos mensuales emparejados, 10.000
réplicas, semilla 20261009. Es una aproximación y no reemplaza a C1 ni a C2.

Se informa por separado de: **rentabilidad** (CAGR), **rentabilidad ajustada al riesgo** (Sharpe y Sortino),
**caídas** (MaxDD) y **costes**.

## 6. Cartera 30/30/40 sin rebalanceo

En la primera apertura del tramo: presupuesto = C0 − 3m = 97 USD, repartido en 30% SPY, 30% VEU y 40% AGG, con 3
órdenes. **Las cantidades no cambian hasta la liquidación final** (3 órdenes más): los pesos evolucionan solos con
los precios. **No hay costes de rebalanceo porque no hay rebalanceo.** Total: 6 órdenes y 6 USD de comisión.

## 7. Variantes y riesgo de selección múltiple

| Id | Cambio |
| --- | --- |
| S1 | Filtro absoluto sobre el activo ganador |
| S2 | Ventana de 6 meses |
| S3 | Ventana de 9 meses |
| S4 | Costes ×2 (m = 2, s = 0,10%) |
| S5 | Capital 50 |
| S6 | Capital 200 |
| S7 | Capital 10.000 |
| S8 | Ejecución al cierre del día de decisión (optimista, no realizable) |

- Se calculan las 8 y se publican todas, incluidas las desfavorables.
- **Ninguna sustituye a la configuración principal ni cambia el veredicto**, aunque alguna cumpla C1 y C2 y la
  principal no. Esto está escrito en `forbidden` y `sensitivity.note` del protocolo.
- S4 solo interviene en la definición de "mejora robusta", que está fijada de antemano.
- **Riesgo de selección múltiple:** ARGOS acumulará 17 pruebas (8 de EXP-001, 1 principal y 8 variantes). Si se
  mirasen las 9 configuraciones de GEM como candidatas, es esperable que alguna salga favorable por azar. Por eso solo
  una cuenta. Las variantes miden fragilidad: si el resultado cambia mucho con ellas, eso se dirá.

## 8. ¿Es 2015–2025 realmente fuera de muestra?

**Para la regla, sí; para el diseño de este experimento, no del todo.**

- **A favor:** las reglas (12 meses, activos, orden de los filtros) las fijó el autor antes de 2015. No se ha
  optimizado nada con datos de 2015–2025.
- **En contra, cosas que ya sabíamos al diseñar:**
  1. EXP-001 ya miró SPY en 2008–2025: sabemos que la tendencia lenta perdió rentabilidad en años alcistas.
  2. **Elegimos GEM** después de leer replicaciones que cubren este mismo periodo y dicen que rindió menos que el
     S&P 500.
  3. **Los criterios** (caídas frente a SPY y rentabilidad frente a una 30/30/40, en vez de frente a SPY) se eligieron
     sabiendo eso. Es razonable, porque compara con una referencia de riesgo parecido, pero no es ciego.
  4. **El umbral de 0,75** lo puse conociendo a grandes rasgos las caídas del S&P 500 en 2020 y 2022, y que en 2022
     también cayeron los bonos. No he calculado nada con esos datos, pero la elección no es independiente.
- **Conclusión:** el resultado será una **verificación de una regla publicada, con costes de capital bajo, sobre un
  periodo conocido**. No es una prueba independiente en sentido estricto. La única prueba independiente sería
  **prospectiva** (datos posteriores al registro), que sigue pendiente de tu decisión.

## 9. Separación de datos entre experimentos

- **EXP-001 no se toca:** ni `data/csv/*.csv`, ni sus originales, ni su protocolo, ni su `LOCKS`, ni su registro.
- EXP-002 usará:
  - `data/csv/EXP-002/`: CSV convertidos;
  - `data/raw/tiingo/`: originales nuevos con su marca de tiempo, sin sobrescribir los existentes; el manifiesto
    solo crece;
  - `data/experiments/EXP-002/`: registro y resultados.
- Implementación (fase 5): una opción de carpeta de salida en `tiingo convertir` y en `data.check`, más un test que
  impida que una conversión de EXP-002 escriba en `data/csv/`. El auditor ya admite `--csv-dir`.

## 10. Implementación prevista (fase 5, después de registrar)

`argos/backtest/portfolio.py` (pesos objetivo, varios activos, comisión mínima, calendario común estricto),
`argos/strategy/gem.py` (con auditoría de truncamiento), métricas en exceso y bootstrap,
`argos/experiments/exp002.py` (`runner.py` de EXP-001 no se toca) y tests sintéticos calculados a mano.
