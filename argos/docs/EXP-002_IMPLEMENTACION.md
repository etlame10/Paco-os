# EXP-002: implementación y validación técnica (fase 5)

> **Estado:** implementado y validado con datos SIMULADOS. **No se ha descargado ningún dato real, no se ha
> ejecutado EXP-002 y no hay resultados financieros históricos.** El experimento real necesita autorización
> expresa (`--ejecutar`). Los protocolos de EXP-001 y EXP-002 y sus entradas en `LOCKS.json` no se han tocado.

## Arquitectura

```
data/csv/EXP-002/*.csv ──► load_market ──► Market ──► gem_decisions ──► run_period ──► simulate ──► métricas ──► criterios ──► informe
  (solo EXP-002)          calidad, auditoría,        (fin de mes NYSE,   (tramo, entrada,  (órdenes,     (definiciones   (C1, C2,      result.json
                          calendario NYSE estricto   cierres ≤ d(m))     ejecuciones)      costes, V_t)  del protocolo)  bootstrap,    report.md
                                                                                                                         veredicto)    registry.jsonl
```

| Fichero | Qué hace |
| --- | --- |
| `argos/backtest/portfolio.py` | Motor de pesos objetivo con varios activos, independiente de la estrategia. Implementa la comisión `max(m, p·importe)`, el deslizamiento, la venta total antes de comprar, la liquidación final al cierre y la regla de efectivo insuficiente. También contiene las métricas del protocolo: MaxDD con V_0, CAGR con días naturales, Sharpe y Sortino en exceso sobre BIL, volatilidad, años naturales y meses. |
| `argos/strategy/gem.py` | Regla principal y variante S1, y ventana de 6, 9 o 12 meses. El día de decisión sale del **calendario NYSE**, no de los datos, así que truncar los datos no puede convertir un día cualquiera en fin de mes. Solo usa cierres hasta d(m). |
| `argos/experiments/exp002.py` | Ejecutor de EXP-002: carga estricta, tramos, referencias, 9 configuraciones (principal + S1–S8), comprobaciones contables, auditoría anti look-ahead, bootstrap, veredicto, informe, registro propio, ensayo sintético y línea de comandos protegida. |
| `argos/experiments/storage.py` | Carpetas por experimento y elección de la descarga cuyo rango coincide **exactamente** con el del protocolo. |

### Cambios en código existente (sin efecto en EXP-001)

| Fichero | Cambio | Motivo |
| --- | --- | --- |
| `argos/tools/tiingo.py` | `convertir` escribe en la carpeta del protocolo y convierte la descarga con el rango del protocolo, no la más reciente. | Antes, una descarga de SPY para EXP-002 se habría usado al reconvertir EXP-001. |
| `argos/data/check.py` | Con `--protocolo EXP-00N` y sin `--dir`, lee `data/csv/EXP-00N/`. | Separación de datos. Con EXP-001 no cambia. |
| `argos/data/audit.py` | `--csv-dir` toma por defecto la carpeta del protocolo. | Ídem. Con EXP-001 sigue siendo `data/csv/`. |

`runner.py` de EXP-001 no se ha tocado en esta fase. Sigue rechazando EXP-002 desde el registro.

### Separación de datos

| | EXP-001 | EXP-002 |
| --- | --- | --- |
| CSV convertidos | `data/csv/` | `data/csv/EXP-002/` (prohibido escribir en `data/csv/`) |
| Originales | `data/raw/tiingo/` (rango 2007-01-01 → 2025-12-31) | `data/raw/tiingo/` (rango 2007-06-01 → 2026-09-30), en ficheros nuevos |
| Resultados y registro | `data/experiments/registry.jsonl` | `data/experiments/EXP-002/` (`resultados/`, `ensayos/`, `registry.jsonl`) |

## Reglas implementadas y comprobaciones automáticas en cada ejecución

- **Calendario:** las sesiones del mercado son exactamente las NYSE de 2007-06-01 a 2026-09-30. Una sesión ausente,
  una fecha que no es sesión o una fila fuera del rango (incluida la reserva desde 2026-10-01) dejan el experimento
  **inconcluso**. Nunca se rellena.
- **Datos:** control de calidad (13 comprobaciones). Si es un experimento real, también auditoría con procedencia y
  original intacto. Un bloqueo o un fallo dejan el resultado inconcluso. Si en un experimento real aparece algún
  fichero `DEMO-*` (simulado), el resultado es inconcluso.
- **Tramos:** cada tramo es independiente y empieza con C0 en efectivo. La entrada se hace en la primera apertura con
  la última decisión previa. Las decisiones cuya ejecución caería fuera del tramo no se ejecutan. La liquidación se
  hace al cierre de la última sesión.
- **Contabilidad** (`accounting_problems`):
  - número de órdenes: 2 + 2K, 2 y 6;
  - comisión por orden y total;
  - deslizamiento de cada orden igual a cantidad·P·s;
  - identidad V_T = C0 + bruto − comisiones − deslizamiento, al céntimo;
  - BIL nunca en cartera;
  - cada cambio se ejecuta en la sesión prevista: la apertura siguiente a la decisión, o su cierre en S8;
  - 0 ≤ K ≤ número de decisiones.
- **Decisiones frente a operaciones:** en la evaluación deben salir 132 decisiones. K y las órdenes se informan
  aparte.
- **Información futura:** cada decisión de las configuraciones con señales distintas (principal, S1, S2 y S3) se
  recalcula con los datos truncados en su propio día y debe salir idéntica. S4–S8 usan las mismas señales que la
  principal.
- **Veredicto:** C1 y C2 sobre la configuración principal en `evaluacion`; "mejora robusta" exige además el IC 95% de
  ΔCAGR por encima de 0 y C1 y C2 en S4. Cualquier fallo contable, de calendario o de efectivo deja el resultado
  inconcluso.

## Interpretaciones de detalle (pendientes de tu confirmación antes de ejecutar)

No contradicen el protocolo, pero este no las fija al pie de la letra. Se aplican así y salen en cada informe:

1. **Sharpe y Sortino diarios:** e_1 usa V_0 = C0 y el cierre de BIL de la sesión anterior al tramo, que es un dato
   pasado.
2. **ΔSharpe del bootstrap:** Sharpe mensual **en exceso sobre BIL**, como todos los Sharpe del protocolo. BIL se
   remuestrea con los mismos bloques.
3. **Semilla del bootstrap:** un generador nuevo `default_rng(20261009)` para cada comparación (frente a SPY y frente
   a la 30/30/40).
4. **Peor año y regímenes:** solo años naturales completos.
5. **Volatilidad:** desviación típica de los rendimientos diarios (ddof = 1) × √252.
6. **S8:** la entrada sigue la regla del tramo (primera apertura). Si una decisión cae en la última sesión, se
   ejecuta al cierre y luego se liquida (lectura literal). En la configuración principal esto no puede pasar.
7. **Alcance de "inconcluso":** la falta de efectivo o un fallo contable en **cualquier** configuración deja
   inconcluso el experimento entero ("en algún momento").

## Tests (todos con datos inventados)

| Tipo | Fichero | Tests | Qué cubre |
| --- | --- | --- | --- |
| Unitarios | `tests/test_portfolio_engine.py` | 18 | Compra, venta y liquidación calculadas a mano; sin orden si no cambia el objetivo; órdenes 2 + 2K, 2 y 6; 30/30/40 sin rebalanceo con pesos libres; dividendos a través de precios ajustados; ejecución al cierre; efectivo insuficiente; precios ≤ 0, NaN o infinitos; mercado mal formado; validación de ejecuciones; comisión porcentual; MaxDD con V_0, CAGR, Sharpe, Sortino y volatilidad en exceso; años y meses. |
| Unitarios | `tests/test_gem_strategy.py` | 16 | Tabla de verdad de la regla principal y de S1 (incluidos empates y el único caso en que difieren); fines de mes NYSE (31-12-2014, 28-11-2025, Viernes Santo de 2018); momentum con ventanas de 6, 9 y 12; truncamiento; cambiar precios futuros o aperturas no altera decisiones pasadas; el cierre del día de decisión sí; un mes incompleto no es decisión. |
| Integración | `tests/test_exp002_runner.py` | 20 | Carga de 4 CSV simulados de 2007 a 2026; sesión ausente, fecha no NYSE, fila de la reserva, precio negativo, texto no numérico y fichero ausente → inconcluso; variantes = protocolo; tramo de evaluación con 132 decisiones, entrada el 2015-01-02, cambios en la apertura siguiente y liquidación el 2025-12-31; métricas recalculadas a mano; K = 0 da la misma curva que comprar y mantener SPY; S8; capital insuficiente; tramo sin sesiones o sin decisión previa; la auditoría detecta una señal que mira el futuro; bootstrap reproducible; ensayo completo que solo escribe en su carpeta; el modo real rechaza datos simulados; protocolo o registro alterados bloquean; la línea de comandos sin opciones no simula. |
| Integración | `tests/test_exp002_storage.py` | 5 | Carpetas por experimento; con un Tiingo falso, la conversión de EXP-002 va a `data/csv/EXP-002/` y no toca `data/csv/`, y EXP-001 sigue convirtiendo su propia descarga aunque haya otra más reciente; sin descarga del rango no se convierte; `check` y `audit` usan la carpeta del protocolo; dividendos y split del original llegan al motor como rentabilidad total. |

**Ninguna de estas pruebas dice nada sobre si GEM funciona.** Los precios son inventados, y los veredictos que salen
en los tests o en el ensayo no tienen ningún valor.

## Uso

```bash
python -m argos.experiments.exp002                      # comprobación previa: bloqueo y ficheros. No simula.
python -m argos.experiments.exp002 --ensayo-sintetico   # ENSAYO con datos simulados → data/experiments/EXP-002/ensayos/
# Solo tras autorización expresa:
python -m argos.tools.tiingo descargar --protocolo EXP-002
python -m argos.tools.tiingo convertir --protocolo EXP-002
python -m argos.data.audit --protocolo EXP-002 --salida auditoria_EXP-002.md
python -m argos.experiments.exp002 --ejecutar
```

## Limitaciones conocidas de la implementación

- El calendario NYSE se validó contra una librería independiente para 2000–2025. Para 2026 se aplican las reglas del
  calendario sin esa validación, así que un cierre extraordinario en 2026 aparecería como "sesión ausente" y dejaría
  el experimento inconcluso; no se rellenaría.
- La auditoría de procedencia requiere los `.source.txt` y los originales. Si falta el original, el resultado queda
  "no comprobable" y no bloquea, igual que en EXP-001.
- El bootstrap es una aproximación (bloques de 12 meses sobre unos 132 meses) y no sustituye a C1 ni a C2.
