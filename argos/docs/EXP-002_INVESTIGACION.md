# EXP-002: inspección del repositorio e investigación de fuentes (fases 1 y 2)

> **Estado:** solo inspección e investigación. **No hay protocolo de EXP-002**, no se ha descargado ningún dato,
> no se ha ejecutado ningún backtest y **no se declara ninguna estrategia ganadora**.
> EXP-001 no se ha modificado: solo se ha consultado en modo lectura (ver §1.3).

Leyenda usada en todo el documento:

| Etiqueta | Significado |
| --- | --- |
| **[VERIFICADO]** | Comprobado directamente en este repositorio (comando y salida reproducibles). |
| **[PUBLICADO]** | Resultado publicado por terceros. ARGOS no lo ha recalculado. |
| **[ARGOS]** | Resultado calculado por ARGOS. |
| **[HIPÓTESIS]** | Idea aún no comprobada. |
| **[NO VERIFICADO]** | No he podido contrastarlo con la fuente primaria. Debe comprobarse antes de citarse. |

**Limitación de la investigación (importante).** El entorno en el que se hizo esta revisión bloquea la descarga
directa de SSRN, mebfaber.com y optimalmomentum.com. Las afirmaciones bibliográficas proceden de búsquedas
(resúmenes oficiales, fichas editoriales y reseñas de terceros), **no de leer los PDF completos**. Por eso las cifras
de rentabilidad publicadas se dan con su fuente secundaria y marcadas; antes de fijar el protocolo conviene que
alguien lea los originales (enlaces en §2.6).

---

## 1. Fase 1: inspección del repositorio

### 1.1 Estado de Git y del entorno **[VERIFICADO]**

| Elemento | Valor |
| --- | --- |
| Rama | `claude/eloquent-lamport-8cag28` (sincronizada con `origin`) |
| Último commit antes de este documento | `a45d915` (compatibilidad con Windows) |
| Árbol de trabajo | limpio |
| Tests | `276 passed` (Linux, Python 3.13.16, `python -m pytest`) |
| Dependencias | pandas 3.0.6, numpy 2.5.3, pydantic 2.13.5, fastapi 0.142.4, certifi 2026.7.22, pytest 9.1.1 |
| Huella de `protocols/EXP-001.json` | `7f553e110fff59245a96504bdd0107b179550164eaf3800cbe8664f34cc98cce` = la de `LOCKS.json` |
| Datos reales en este entorno | **ninguno**: `data/csv/` está vacío y `data/raw/` no existe. Los datos de Tiingo están en el equipo del usuario (y por diseño no se suben a Git). |

### 1.2 Arquitectura relevante para EXP-002 **[VERIFICADO]**

Lo que ya sirve:

- **Datos:** proveedor CSV estricto, descarga y conversión mecánica de Tiingo (precios `adj*`, ajuste multiplicativo
  por dividendos y splits), manifiesto con SHA-256, control de calidad de 13 comprobaciones, auditoría profunda con
  calendario NYSE.
- **Experimentos:** protocolo JSON con huella en `LOCKS.json`, registro solo-añadir, separación de ensayos
  (`dry_run`), análisis por regímenes anuales.
- **Motor:** señal al cierre de *t* → ejecución a la apertura de *t+1*; comisión y deslizamiento proporcionales;
  auditoría anti look-ahead por truncamiento.

Lo que **falta** para las estrategias candidatas (se implementaría en la fase 5, no ahora):

1. **Cartera multi-activo.** `Backtester` solo maneja *un activo o liquidez*. Dual momentum rota entre activos y el
   modelo de Faber reparte entre varios.
2. **Rentabilidad de la liquidez.** Hoy la liquidez rinde 0%. Las dos familias usan letras del Tesoro como refugio
   o como umbral.
3. **Comisión mínima fija** (p. ej. 1 € por orden). Con capital bajo es el coste dominante (ver §3.3) y el motor
   no la modela.
4. **Calendario de decisión mensual** (último día hábil del mes).
5. **Sharpe con tasa libre de riesgo.** `metrics.sharpe` admite `risk_free`, pero el ejecutor de EXP-001 usa 0.
6. **Sortino**, rotación anual y coste total como métricas registradas.
7. **Criterios de éxito genéricos.** `runner.py` tiene codificado "3 de 4 activos principales" de EXP-001. EXP-002
   necesita su propio evaluador. EXP-001 no se tocaría.

### 1.3 Cómo se usa EXP-001 aquí (solo lectura)

- Protocolo, hash, `LOCKS.json` y registro: **no se modifican**.
- Resultados: los ejecutó el usuario en su equipo (commit `a45d915`). Aquí solo se citan como antecedente, tal y
  como los comunicó el usuario. **No se han recalculado.**
- **Contaminación reconocida.** Los resultados de EXP-001 ya influyen en este diseño: sabemos que el cruce 50/200
  redujo caídas en años bajistas y perdió mucha rentabilidad en años alcistas. Por eso SPY 2008–2025 **no es un
  conjunto virgen** para EXP-002 y no puede presentarse como prueba independiente.
- **Contaminación más amplia, que no se puede evitar.** Cualquier persona que diseñe hoy una estrategia conoce la
  historia de 2008, 2020 y 2022. Ningún tramo histórico es ciego para el investigador. La única prueba de verdad
  independiente es **prospectiva**: datos que todavía no existen cuando se fija el protocolo (ver §3.6).

---

## 2. Fase 2: revisión bibliográfica

### 2.A Seguimiento de tendencia: media móvil de 10 meses (Faber)

| Punto | Contenido |
| --- | --- |
| 1. Fuente | Mebane T. Faber, *A Quantitative Approach to Tactical Asset Allocation*, The Journal of Wealth Management 9(4), 2007, pp. 69–79, DOI 10.3905/jwm.2007.674809; SSRN 962461. Actualización de 2013 en la misma ficha de SSRN. **[PUBLICADO]** |
| 2. Reglas | Al **cierre de mes**: si el precio mensual > media simple de 10 meses → invertido; si no → liquidez (letras del Tesoro). Cartera "GTAA": 5 clases de activo a partes iguales (20% cada una), cada una con su propio filtro. Decisión mensual. |
| 3. Activos | Acciones de EE. UU., acciones internacionales desarrolladas, bonos del Tesoro de EE. UU., inmuebles cotizados (REIT) y materias primas, con series de índices de rentabilidad total. Análisis histórico desde 1901 para la renta variable de EE. UU. **[PUBLICADO, vía reseñas]** |
| 4. Resultados | Según reseñas de la actualización de 2013, con la cartera GTAA en 1973–2012: el filtro rindió 10,5% anual frente a 9,9% de comprar y mantener, con caída máxima mucho menor (el original cita un paso de ≈46% a un dígito). **[NO VERIFICADO: las reseñas truncan o mezclan cifras; consultar las tablas originales.]** |
| 5. Replicaciones | **Zakamulin**: *Fooled by Data-Mining* (2013), *A Comprehensive Look at the Empirical Performance of Moving Average Trading Strategies* (SSRN 2677212) y el libro *Market Timing with Moving Averages* (Palgrave, 2017). Conclusiones, según sus resúmenes: el resultado de Faber está afectado por *data-mining*; fuera de muestra las reglas de media móvil **reducen sobre todo el riesgo**, con una ventaja pequeña e inestable; hay muchas señales falsas; el valor se concentra en mercados bajistas; y **no hay superioridad estadísticamente significativa en la segunda mitad de la muestra**. **[PUBLICADO, vía resúmenes]** |
| 6. Costes y ejecución | El original ignora impuestos y, según una fuente secundaria, ejecuta al **mismo cierre** que genera la señal (ARGOS ejecutaría a la apertura siguiente, que es más estricto). Zakamulin usa un 0,25% por operación. **[Ejecución al mismo cierre: NO VERIFICADO en el PDF.]** |
| 7. Limitaciones | Periodo elegido por el autor; la longitud de 10 meses no se justifica fuera de muestra (Zakamulin la encuentra como óptima *a posteriori* en su muestra, lo que es otra señal de selección); en mercados alcistas con correcciones rápidas (2018, 2020) produce *whipsaw*. Con varios activos, cada uno es una operación independiente, lo que pesa mucho con poco capital. |
| 8. Dificultad de replicar | **Baja** en reglas y **media** en datos: hacen falta ETF de las 5 clases. Algunos empiezan en los 2000, así que el periodo útil con ETF es mucho más corto que el del artículo. |
| 9. Hipótesis para ARGOS | **[HIPÓTESIS]** Aplicada a ETF, con ejecución en la apertura siguiente y costes reales de capital bajo, la regla de 10 meses **reduce la caída máxima** frente a la cartera equiponderada estática equivalente, **sin** mejorar la rentabilidad neta. |

**Relación con EXP-001.** El cruce 50/200 diario y el filtro de 10 meses son primos cercanos: ambos son tendencia a
largo plazo de "dentro o fuera". EXP-001 ya apuntó a lo que dice la literatura: menos caída en años bajistas y mucha
rentabilidad perdida en los alcistas. Repetir una regla casi igual sobre activos parecidos aportaría poca
información nueva. Su interés en EXP-002 sería la **diversificación entre clases de activo** y la **decisión
mensual**.

### 2.B Dual momentum (Antonacci)

| Punto | Contenido |
| --- | --- |
| 1. Fuente | Gary Antonacci, *Risk Premia Harvesting Through Dual Momentum*, SSRN 2042750 (borrador de 2012; publicado en *Journal of Management & Entrepreneurship* 11(1), 2017), y el libro *Dual Momentum Investing*, McGraw-Hill, 2014. **[PUBLICADO]** |
| 2. Reglas (GEM) | Cada mes, con rentabilidad total de **12 meses**: (a) **momentum relativo**: elegir entre renta variable de EE. UU. (S&P 500) y fuera de EE. UU. (MSCI ACWI ex-US) la que más subió; (b) **momentum absoluto**: si la renta variable **no** supera a las letras del Tesoro en 12 meses, invertir en **bonos agregados de EE. UU.**. Siempre un único activo al 100%. **Ambigüedad documentada:** unas fuentes aplican el filtro absoluto al activo elegido y otras (Petit, 2026) al S&P 500 frente a las letras. Hay que fijar la versión en el protocolo citando el libro. **Actualización:** los extractos de la web del autor describen el S&P 500 como primer filtro; ver [EXP-002_DISENO.md §1](EXP-002_DISENO.md). |
| 3. Activos | Índices de renta variable de EE. UU. y global ex-US, bonos agregados de EE. UU. y letras del Tesoro como umbral. |
| 4. Resultados del autor | 1974–2013, según reseñas del libro: ≈17,4% anual, Sharpe ≈0,87 y caída máxima ≈22,7%, frente a ≈8,9% anual y una caída del 45,7% al 60% del índice global (las reseñas no coinciden). **Bruto de costes**, con ≈1,35 cambios al año. **[PUBLICADO por el autor; NO VERIFICADO en el libro.]** |
| 5. Replicaciones | **Petit (SSRN 7427878, preprint fechado en septiembre de 2026; sin revisión por pares):** 1971–2026, 15,18% frente a 11,27% del S&P 500, caída máxima del 21,7% frente al 50,9%, ≈1,5 operaciones al año. Atribuye el exceso a la combinación de los dos filtros, no a la diversificación. También indica que **desde 2010 GEM queda ≈4,8 puntos al año por debajo del índice**. **[NO VERIFICADO: solo he visto el resumen; el preprint es posterior a mi información de referencia.]** **ThinkNewfound (2019), *Fragility Case Study: Dual Momentum GEM*:** el resultado anual cambia en cientos o miles de puntos básicos según detalles de implementación (día del mes, longitud de la ventana). **Price Action Lab (2023)** y **Quant for Free:** el rendimiento empeora tras la publicación, quedando por debajo de SPY y de un 60/40. **[PUBLICADO por terceros; blogs, sin revisión por pares]** |
| 6. Costes y ejecución | El autor publica resultados brutos y argumenta que con ≈1,4 operaciones al año los costes son pequeños. Eso vale con capital normal; con 100 € y una comisión mínima de 1 €, no (ver §3.3). |
| 7. Limitaciones | Fuerte dependencia de la ruta (*path dependency*): una sola decisión al mes y un solo activo hacen que un día de diferencia cambie el año. Rinde por debajo al inicio de los mercados alcistas (lo admite el propio autor en su FAQ). La muestra de 1974–2013 coincide con 30 años de tipos de interés a la baja, lo que favorece al refugio en bonos. Concentración del 100% en un solo activo. Resultados del autor no independientes. **Desde su publicación (2014), los análisis independientes indican que ha quedado por debajo del S&P 500.** |
| 8. Dificultad de replicar | **Baja.** Necesita 4 series: SPY, un ETF ex-US (VEU o ACWX; EFA es un sustituto solo de desarrollados), AGG y BIL. Los ETF ex-US amplios empiezan hacia 2007–2008, así que el periodo con ETF es casi entero **posterior** a la publicación del borrador (2012). |
| 9. Hipótesis para ARGOS | **[HIPÓTESIS]** Con ETF, ejecución en la apertura siguiente y comisión mínima real, GEM **reduce la caída máxima** frente a SPY y frente a un 60/40 fijo. La evidencia posterior a la publicación **no apoya** que mejore la rentabilidad neta. |

### 2.C Referencia pasiva

- **Comprar y mantener SPY** (como en EXP-001) es la referencia mínima, pero no es justa para estrategias que pasan
  tiempo en bonos: compara riesgos distintos.
- **Referencia equivalente propuesta:** carteras estáticas con rebalanceo anual y los mismos activos:
  - para GEM: 60% renta variable (SPY y ex-US a partes iguales) + 40% AGG;
  - para el modelo de Faber: los 5 ETF al 20%.

  Así se separa lo que aporta la **regla** de lo que aporta la **diversificación**, que es la descomposición que
  hace Petit. Los pesos se fijan *a priori* y no salen de la asignación media observada de la estrategia, porque esa
  media solo se conoce después.
- Con capital bajo, la referencia pasiva realista es **un único ETF de renta variable global**. Una cartera de
  varios ETF también paga comisiones mínimas.

### 2.D ¿Una cuarta familia?

| Candidata | Evidencia | Recomendación |
| --- | --- | --- |
| **Momentum de serie temporal multi-activo** (Moskowitz, Ooi y Pedersen, JFE 104, 2012; Hurst, Ooi y Pedersen, JPM 44(1), 2017: 67 mercados desde 1880) | Es la más sólida de todas. **[PUBLICADO]** Pero se estudió con **futuros, posiciones cortas, apalancamiento y objetivo de volatilidad del 10%**. Kim, Tse y Wald atribuyen gran parte del exceso al escalado por volatilidad. | **No incluirla.** No se puede replicar con 100 €, solo largos y ETF. Sirve como respaldo teórico de A y B, no como estrategia. |
| **Gestión por volatilidad** (Moreira y Muir, JF 72(4), 2017) | Cederburg, O'Doherty, Wang y Yan (JFE 138, 2020): en 103 estrategias, las versiones aplicables en tiempo real **rinden por debajo** de las originales en la mayoría de casos (72 de 103 según un resumen). DeMiguel et al. (JF, 2024) defienden una versión multifactor. Evidencia **disputada**. **[PUBLICADO]** | **No incluirla como candidata principal.** Requiere rebalanceos frecuentes (malo con comisión mínima) y su evidencia fuera de muestra es débil. |

**Conclusión:** no propongo una cuarta familia. Añadirla aumentaría el número de pruebas, y con él el riesgo de
encontrar un ganador por azar, sin evidencia aplicable a este caso.

### 2.E Evidencia transversal que condiciona el diseño

- **Decaimiento tras la publicación.** McLean y Pontiff, *Does Academic Research Destroy Stock Return
  Predictability?*, Journal of Finance, 2016: en 97 predictores, la rentabilidad cae ≈26% fuera de muestra y ≈58%
  tras la publicación. **[PUBLICADO]** Es esperable que A y B rindan menos que en sus artículos.
- **Umbral estadístico.** Harvey, Liu y Zhu, RFS 29(1), 2016: dado el volumen de *data-mining*, un hallazgo nuevo
  debería exigir *t* > 3,0 y no 2,0. **[PUBLICADO]**
- **Sobreajuste del backtest.** Bailey y López de Prado, *The Deflated Sharpe Ratio*, JPM 40(5), 2014; Bailey,
  Borwein, López de Prado y Zhu, *The Probability of Backtest Overfitting*, J. Computational Finance, 2017.
  Corrigen el Sharpe por el número de pruebas realizadas. **[PUBLICADO]**
- **Ejecución realizable.** Zakamulin (2018, *Revisiting the Profitability of Market Timing with Moving Averages*)
  muestra que un resultado "demasiado bueno" de otro estudio se debía a look-ahead. ARGOS ya ejecuta en la apertura
  siguiente.

### 2.F Tabla comparativa

| | Comprar y mantener | Faber 10 meses (GTAA-5) | Dual momentum (GEM) |
| --- | --- | --- | --- |
| Activos en cartera a la vez | 1 | hasta 5 | **1** |
| Decisiones | ninguna | mensual por activo | mensual |
| Operaciones al año | ≈0 | varias por activo **[NO VERIFICADO]** | ≈1,4–1,5 **[PUBLICADO]** |
| Lo que dice la evidencia independiente | referencia difícil de batir | menos riesgo, ventaja pequeña e inestable | menos caída; peor que el S&P 500 desde 2010–2014 |
| Encaje con 100 € y comisión mínima | bueno | **malo** (5 posiciones de 20 €) | **aceptable** |
| Riesgo específico | caídas del 50% | *whipsaw* | dependencia de la ruta y concentración |
| Parecido a EXP-001 | — | alto | medio |

### 2.G Fuentes

Fuentes primarias (fichas oficiales; los PDF no se pudieron descargar desde este entorno):

- Faber (2007/2013). SSRN 962461: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>. Copia del autor:
  <https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf>
- Antonacci (2012/2017). SSRN 2042750: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750>
- Antonacci, *Dual Momentum Investing* (McGraw-Hill, 2014). Web del autor:
  <https://www.optimalmomentum.com/global-equities-momentum/>. FAQ: <https://www.optimalmomentum.com/faq/>
- Moskowitz, Ooi y Pedersen (2012). SSRN 2089463: <https://papers.ssrn.com/abstract=2089463>
- Hurst, Ooi y Pedersen (2017):
  <https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing>
- Moreira y Muir (2017). NBER w22208: <https://www.nber.org/papers/22208>
- Cederburg et al. (2020): <https://www.lehigh.edu/~xuy219/research/COWY.pdf>
- McLean y Pontiff (2016): <https://ivey.uwo.ca/media/3775549/pontiff.pdf>
- Harvey, Liu y Zhu (2016). NBER w20592: <https://nber.org/papers/w20592>
- Bailey y López de Prado (2014). SSRN 2460551: <https://papers.ssrn.com/abstract=2460551>
- Bailey et al., PBO. SSRN 2326253: <https://papers.ssrn.com/abstract=2326253>
- Zakamulin. SSRN 2677212: <https://papers.ssrn.com/abstract=2677212>

Replicaciones y críticas (sin revisión por pares salvo indicación):

- Petit (2026, preprint). SSRN 7427878: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7427878>
- ThinkNewfound (2019): <https://blog.thinknewfound.com/2019/01/fragility-case-study-dual-momentum-gem/>
- Price Action Lab (2023): <https://www.priceactionlab.com/Blog/2023/03/dual-momentum/>
- Quant for Free: <https://quant4free.com/analysis/dual-momentum/>
- CXO Advisory sobre Zakamulin:
  <https://www.cxoadvisory.com/technical-trading/market-timing-with-moving-averages-over-the-very-long-run>
- CXO Advisory sobre el libro de Antonacci:
  <https://www.cxoadvisory.com/momentum-investing/a-few-notes-on-dual-momentum-investing/>
- justETF, ETF domiciliados en EE. UU. y PRIIPs: <https://www.justetf.com/en/news/etf/us-domiciled-etfs.html>

---

## 3. Implicaciones para el diseño (anticipo de la fase 3, sin fijar nada)

### 3.1 Lo que la evidencia permite esperar, sin maquillar

- La evidencia independiente apoya, con matices, que estas reglas **reducen las grandes caídas**.
- **No** apoya de forma sólida que **mejoren la rentabilidad neta** tras su publicación.
- El objetivo de "solo ganancias con margen de error pequeño" **no está respaldado por ninguna de las fuentes
  revisadas**. Ambas estrategias tienen años negativos publicados por sus propios autores.
- La hipótesis principal honesta para EXP-002 es de **reducción de caídas a un coste de rentabilidad medido**, no
  de batir al mercado.

### 3.2 Recomendación de candidatas

1. **Principal: GEM**, en la versión del libro (fijando la ambigüedad del filtro absoluto citando la página).
   Motivos: una sola posición, pocas operaciones, información nueva respecto a EXP-001 (rotación y refugio en
   bonos) y existencia de replicaciones y críticas con las que contrastar.
2. **Secundaria: filtro de 10 meses sobre un único ETF de renta variable**. Comprueba si la versión mensual y más
   simple de lo que probó EXP-001 se comporta distinto, con costes de capital bajo.
3. **No recomendada: GTAA-5 completa.** Se evaluaría solo como análisis descriptivo con capital de referencia
   (p. ej. 10.000 €), nunca como candidata para 100 €.

Máximo propuesto: **2 estrategias candidatas** más sus referencias pasivas, y una rejilla pequeña de sensibilidad
fijada de antemano: ventanas de 6, 9 y 12 meses para GEM y de 8, 10 y 12 para el filtro. La sensibilidad se
**publica, pero no se usa para elegir parámetros**. Todo cuenta como pruebas realizadas, incluidas las 8 de
EXP-001.

### 3.3 Aritmética de costes con capital bajo (no es un resultado de mercado)

Supuestos: comisión mínima *m* = 1 € por orden y capital *C*. Un cambio de activo son 2 órdenes (venta + compra).

| Capital | Coste por orden | Coste por cambio | Con ≈1,5 cambios al año (cifra publicada para GEM) |
| --- | --- | --- | --- |
| 50 € | 2% | 4% | ≈6% anual |
| 100 € | 1% | 2% | ≈3% anual |
| 200 € | 0,5% | 1% | ≈1,5% anual |
| 500 € | 0,2% | 0,4% | ≈0,6% anual |

Además hay que sumar diferencial de compra-venta, comisiones de cambio de divisa e impuestos (no modelados).
**Con 50–100 € la comisión mínima puede comerse la diferencia que la literatura atribuye a estas estrategias.**
Es un motivo de peso para medir los costes reales del broker antes de fijar el protocolo. Algunos brokers ofrecen
planes de ahorro sin comisión, pero no lo he verificado y suelen ejecutar en fechas fijas, no cuando la regla
decide.

### 3.4 Restricción regulatoria para un inversor minorista en la UE **[PUBLICADO, justETF; NO VERIFICADO en el texto legal]**

Por PRIIPs (Reglamento UE 1286/2014), un minorista en la UE normalmente **no puede comprar ETF domiciliados en
EE. UU.** (SPY, AGG, BIL…), porque no publican el documento KID. Se usan equivalentes UCITS domiciliados en Irlanda
o Luxemburgo. Consecuencias:

- Los datos de Tiingo de los ETF de EE. UU. son un **sustituto de investigación**, no los instrumentos que se podrían
  comprar.
- Los UCITS tienen historiales más cortos, otra divisa y otro tratamiento de dividendos (acumulación). Hay que
  documentarlo como limitación y, si se quiere, añadir una comprobación con UCITS en un experimento aparte.

### 3.5 Datos necesarios (no se ha descargado nada)

- GEM: SPY, un ETF ex-US amplio (VEU o ACWX; EFA es alternativa solo de desarrollados), AGG y BIL.
- Filtro de 10 meses: el ETF de renta variable elegido y BIL.
- Fechas de inicio en Tiingo: **por comprobar**. Las conozco solo de forma aproximada (≈2007–2008 para VEU, ACWX y
  BIL), así que el periodo común útil probablemente empieza hacia **2008**. Eso deja todo el periodo **después** de
  la publicación de Faber (2007) y casi entero después del borrador de Antonacci (2012): una ventaja, porque lo que
  se mediría es el comportamiento posterior a la publicación.
- Todo pasa por la cadena existente: originales intactos, manifiesto SHA-256, conversión mecánica y auditoría.

### 3.6 Periodos y la única prueba realmente independiente

- 2008–2016 (desarrollo) y 2017–2025 (validación) **no son vírgenes**: EXP-001 ya miró SPY en ambos, y la historia
  del mercado es conocida.
- 2026 estaba reservado en EXP-001. Hoy (9 de octubre de 2026) ya ha transcurrido en su mayor parte y es corto
  (menos de 10 decisiones mensuales).
- **[Propuesta pendiente de aprobación]** Una **evaluación prospectiva** sin dinero: desde la fecha de registro del
  protocolo, ARGOS anota cada fin de mes la señal que habría dado la regla y, a final de periodo (p. ej. 24 meses),
  se evalúa con datos que no existían al fijarlo. No conecta con ningún broker ni simula órdenes en tiempo real:
  solo registra señales con fecha y huella. Lo dejo como decisión tuya porque se parece al *paper trading* que
  quedó fuera en fases anteriores.

---

## 4. Decisiones pendientes de tu aprobación

1. **Candidatas:** ¿GEM como principal y filtro de 10 meses sobre un único ETF como secundaria? ¿GTAA-5 solo como
   análisis descriptivo, o fuera?
2. **Hipótesis principal:** ¿centrada en la reducción de la caída máxima con un límite de pérdida de rentabilidad,
   en lugar de en batir al mercado?
3. **Capital y costes:** capital inicial (50, 100 o 200 €), comisión mínima y porcentual de tu broker, y diferencial.
   Sin esto, el diseño usaría 100 € y 1 € como supuesto prudente y lo marcaría como supuesto.
4. **Versión exacta del filtro absoluto de GEM** (sobre el activo elegido o sobre el S&P 500). Requiere leer el
   libro o el artículo original; propongo fijarla citando la página.
5. **Referencias pasivas:** SPY y carteras estáticas equivalentes (60/40 para GEM). ¿De acuerdo?
6. **Evaluación prospectiva** (§3.6): ¿se incluye?
7. **Lectura de originales:** ¿puedes descargar tú los PDF de Faber (mebfaber.com) y Antonacci (SSRN) y dejarlos
   fuera de Git para que contraste las cifras marcadas como NO VERIFICADO? Este entorno no puede descargarlos.
8. **Instrumentos UCITS:** ¿investigación con ETF de EE. UU. como sustituto, documentando la limitación, o quieres
   que se estudie también la disponibilidad de datos UCITS?

Hasta que respondas, no se escribirá `protocols/EXP-002.json`, no se tocará código y no se descargará ningún dato.
