# EXP-002: diseño (fase 3, revisión metodológica v2)

> **Estado: BORRADOR v2, pendiente de autorización explícita.** Protocolo propuesto:
> [`borradores/EXP-002.json`](borradores/EXP-002.json). **No** está en `protocols/` ni en `LOCKS.json`. No se ha
> descargado ningún dato, no hay código nuevo, no se ha ejecutado EXP-002 y EXP-001 no se ha tocado.
> Antecedentes y fuentes: [EXP-002_INVESTIGACION.md](EXP-002_INVESTIGACION.md).

Leyenda: **[CONFIRMADO]** = visto en una fuente del autor (aunque sea a través de extractos de búsqueda);
**[PENDIENTE]** = interpretación no verificada en el libro; **[DECISIÓN]** = elección de diseño nuestra.

## Cambios respecto al borrador v1

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

Las dos versiones solo difieren en un caso: VEU gana a SPY, VEU supera a las letras y SPY no. Entonces la versión
del autor va a bonos y S1 se queda en VEU.

**Recomendación:** antes de autorizar, que alguien con el libro compruebe la página donde se describe GEM. Si no es
posible, se registra tal cual, con la limitación anotada en `source_status`.

## 2. Moneda y capital **[DECISIÓN]**

- El backtest trabaja en **USD**, la moneda de los precios: capital C0 = **100 USD** y comisión m = **1 USD por orden**.
- **No se modela el EUR/USD.** Para un inversor en euros, el valor de todas las carteras se multiplicaría por un tipo
  de cambio que varía cada día. Eso no altera qué activo elige GEM, pero sí la profundidad de las caídas medidas en
  euros, y no lo hace igual en cada cartera.
- Aproximación honesta: 1 EUR estuvo, a grandes rasgos, entre 0,95 y 1,40 USD en 2015–2025. Es una cifra de
  conocimiento general, **no verificada con datos**. Las variantes S4 (comisión de 2), S5 (capital 50) y S6 (capital
  200) **acotan** el caso de 100 EUR y 1 EUR, pero no lo modelan.
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

## 4. Fechas, señales, ejecución, dividendos y calendario

- **Evaluación: 2015-01-01 → 2025-12-31** **[DECISIÓN]**. Es el primer año natural completo tras la publicación del
  libro (octubre de 2014), así que no se elige una fecha de corte a la vista de nada. Hay **132 decisiones**: de
  2014-12-31 a 2025-11-28, comprobado con el calendario NYSE de ARGOS. La primera ejecución es el 2015-01-02.
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

Sobre la curva diaria **V_t**, que vale V_0 = C0 justo antes de la primera apertura del tramo:

```
V_t    = efectivo_t + Σ_i cantidad_i · Pc_i(t)       (cierre de cada sesión; V_final ya liquidado con costes)
MaxDD  = max_t ( 1 − V_t / max_{u≤t} V_u )           (t ∈ {0} ∪ sesiones del tramo)
CAGR   = (V_final / C0)^(365,25 / D) − 1             (D = días naturales entre la primera y la última sesión)

C1:  MaxDD(GEM) ≤ 0,75 · MaxDD(SPY comprar y mantener)
C2:  CAGR(GEM)  ≥ CAGR(30/30/40)
```

Mismo motor, mismas sesiones, mismos precios, mismos costes y mismas métricas para las tres carteras. Solo cambian
los pesos objetivo. Se compara sin redondear.

| Veredicto | Condición |
| --- | --- |
| Mejora robusta | C1 y C2; IC 95% de ΔCAGR(GEM − 30/30/40) entero por encima de 0; y C1 y C2 también con costes ×2 (S4) |
| Indicio no concluyente | C1 y C2, sin el resto |
| No se ha demostrado mejora | Falla C1 o C2 |
| Inconcluso | Datos bloqueados, sesión ausente, menos de 132 decisiones, fallo de la auditoría anti look-ahead, falta de efectivo o necesidad de desviarse del protocolo |

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
