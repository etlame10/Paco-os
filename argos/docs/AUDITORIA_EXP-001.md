# Auditoría de datos y preparación de EXP-001

Fecha: 2026-10-08 · Rama `claude/eloquent-lamport-8cag28` · Base auditada: commit `309667d`.

> **Estado: EXP-001 NO está autorizado todavía.** No se ha ejecutado, ni se ha ejecutado ninguna estrategia con datos reales. Faltan comprobaciones que solo pueden hacerse sobre los CSV reales, que están en el PC del usuario y no en el entorno donde se hizo esta auditoría.

## 1. Qué se ha comprobado realmente

| Área | Comprobado | Cómo | Resultado |
| --- | --- | --- | --- |
| Integridad del protocolo | ✅ | SHA-256 actual frente al commit de pre-registro `6b230de` | Idéntico: `7f553e11…98cce`. Solo `6b230de` ha modificado el fichero. |
| CSV reales del usuario | ❌ **No disponibles aquí** | `data/csv/` vacío y `data/raw/` inexistente en este entorno | **No inspeccionados.** Todo lo relativo a los datos reales queda pendiente (sección 7). |
| Semántica de los campos de Tiingo | ⚠️ Parcial | Documentación pública consultada el 2026-10-08 (ver «Fuentes») | `splitFactor`: confirmado en la documentación oficial de splits. `divCash` y `adj*`: solo fuentes secundarias (la web de Tiingo no es accesible desde este entorno). |
| Por qué «ningún split detectado» | ✅ Explicado en el código | Lectura del código y test con datos sintéticos | La comprobación de splits se hace sobre la serie **ajustada**, donde los splits no producen saltos. No detectarlos es lo esperado y no indica nada. Ver sección 4. |
| Calendario de sesiones NYSE | ✅ | Comparación contra `pandas_market_calendars` 5.5.0 en un entorno temporal | 6.539 sesiones idénticas en 2000-2025. Entre 2007-01-03 y 2025-12-31 hay **4.780**, la misma cifra que cada descarga del usuario. |
| Motor de backtest | ✅ Con datos sintéticos | 10 tests nuevos de propiedades matemáticas | Sin defectos encontrados (sección 4). |
| Seguridad y reproducibilidad | ✅ | Revisión de código y tests | 2 carencias corregidas (sección 4). |

## 2. Pruebas ejecutadas

Todas con datos **sintéticos** generados en los propios tests. **No son evidencia de rentabilidad.**

| Fichero de tests | Qué cubre | Resultado |
| --- | --- | --- |
| `tests/test_audit.py` (nuevo) | Calendario NYSE; split; dividendo; split no declarado; ajuste sin evento; dividendo declarado sin ajuste; factor de split erróneo; sesión que falta; fila en festivo; valores nulos, negativos, no numéricos o NaN; fila cortada; fecha mal escrita; duplicados; precios congelados; histórico truncado; cambio de símbolo o fichero copiado; procedencia ausente; original modificado; CSV editado con la procedencia falsificada; original ausente; CLI | 32 pasan |
| `tests/test_engine_audit.py` (nuevo) | SMA50/200 frente a la definición directa; calentamiento exacto; señal solo en cruces; invariancia de escala; ajuste hacia atrás sin fuga de información futura; dividendos contados una vez; costes no duplicados; precios nulos; datos de 2026 que no alteran resultados | 10 pasan |
| `tests/test_tiingo.py` | Descargas repetidas rechazadas salvo petición expresa; CLI | 2 nuevos + adaptados |
| `tests/test_experiments.py` | Bloqueo de pre-registro antes de la primera ejecución; `LOCKS.json` coincide con el protocolo | 2 nuevos |
| `tests/test_api.py` | Intento de falsificar un registro de EXP-001 desde el navegador | 1 nuevo |
| Suite completa (15 ficheros) | — | **274 pasan, 0 fallan, 0 omitidos** |

**Mutaciones:** se introdujeron 21 errores deliberados en el código nuevo o modificado (dejar de comparar ajustes con eventos, aceptar filas en festivos, olvidar un cierre extraordinario, quitar el bloqueo de pre-registro, permitir descargas repetidas, no reconstruir la conversión…). Todos acaban detectados. Uno (no reconstruir la conversión) sobrevivía al principio; se añadió el test del CSV editado con procedencia falsificada.

## 3. Archivos cambiados

| Archivo | Cambio |
| --- | --- |
| `argos/data/calendar_us.py` (nuevo) | Calendario de sesiones NYSE, validado contra una librería independiente. |
| `argos/data/audit.py` (nuevo) | Herramienta de auditoría `python -m argos.data.audit`. |
| `argos/data/quality.py` | Mensaje de la comprobación de splits aclarado (causa de la confusión). Sin cambios de lógica. |
| `argos/data/sources/tiingo.py` | Función pura `render_converted` (reutilizada por la auditoría, mismo resultado) y protección contra descargas repetidas. |
| `argos/tools/tiingo.py` | Opción `--nueva-descarga`; las descargas ya existentes se omiten. |
| `argos/experiments/protocol.py`, `runner.py` | Comprobación de `LOCKS.json` antes de cualquier ejecución real. |
| `protocols/LOCKS.json` (nuevo) | Huella del protocolo pre-registrado. **`protocols/EXP-001.json` no se ha tocado.** |
| `tests/…` | Tests nuevos y adaptados (sección 2); `tests/synthetic_tiingo.py` genera originales sintéticos. |
| `docs/…`, `README.md` | Esta auditoría y las instrucciones de uso. |

## 4. Defectos corregidos y hallazgos

**Corregidos:**

1. **Mensaje engañoso sobre splits (causa de la duda del usuario).** `quality.py` decía «No se detectan saltos con proporción de split» sobre la serie **ajustada**. En una serie ajustada los splits están suavizados, así que esa comprobación **no puede** ver un split real: solo detecta splits **sin ajustar**. Ahora lo dice explícitamente. Los splits que declara Tiingo (`splitFactor ≠ 1`) los lista el conversor en el `.source.txt` y los contrasta la nueva auditoría.
2. **El bloqueo del protocolo solo actuaba después de la primera ejecución real.** `check_protocol_lock` comparaba con resultados ya registrados; con el registro vacío, un protocolo editado se habría ejecutado. Ahora `protocols/LOCKS.json` guarda la huella pre-registrada y el ejecutor se niega a correr si no coincide. Esto **no modifica la hipótesis ni los criterios**: solo impide que se modifiquen.
3. **Descargas repetidas.** Repetir `descargar` creaba una segunda copia con otros precios ajustados (Tiingo recalcula todo el histórico con cada dividendo) y el conversor usaba la más reciente sin avisar. Ahora una descarga existente no se repite salvo con `--nueva-descarga`.

**Revisados, sin defecto:**

| Punto | Conclusión |
| --- | --- |
| ¿Se usan precios ajustados en la estrategia? | Sí: el conversor copia `adjOpen/adjHigh/adjLow/adjClose/adjVolume`. Señales (cierre) y ejecución (apertura) en la misma escala. |
| ¿Se mezclan series ajustadas y sin ajustar? | No en el CSV. El conversor rechaza filas cuyas cuatro columnas ajustadas no usan el mismo factor. |
| ¿Discontinuidades que generen señales falsas? | No en datos ajustados. Con precios sin ajustar, un split se vería como una caída del ~50 % (test) y el control de calidad lo **bloquea**. |
| ¿Dividendos contados dos veces? | No. Solo entran a través de los precios ajustados. El CSV de ARGOS no contiene `divCash` y el motor no tiene lógica de dividendos (test). |
| ¿Volumen compatible? | Se usa `adjVolume` (ajustado por splits). El backtest no usa el volumen; solo el análisis técnico. |
| ¿Se confunden factores de ajuste con eventos? | Ya no: el mensaje corregido y la auditoría los separan. |
| ¿Sesgo de anticipación por el ajuste hacia atrás? | El ajuste usa eventos futuros para escalar el pasado, pero el cruce de medias solo **compara** precios, y un factor común no cambia la comparación. Test: las señales hasta cada fecha *t* son idénticas a las de una serie ajustada solo con los eventos conocidos en *t*. **Atención:** una regla con umbrales de precio absolutos sí tendría sesgo. |
| Rendimientos, Sharpe, drawdown, costes | Fórmulas comprobadas a mano (tests existentes y nuevos). Sin costes duplicados. |
| Comparación justa con Buy & Hold | Mismo motor, periodo, capital y costes; ambos liquidan al final. |
| Periodos no autorizados | La estrategia nunca ve datos posteriores al fin de cada periodo. Datos de 2026 en el CSV no cambian ningún resultado (test). |

**Convención de dividendos (no es un defecto, conviene saberlo):** el ajuste multiplicativo implica reinvertir el dividendo a `cierre previo − dividendo`. Otra convención habitual da resultados ligeramente distintos (< 0,1 % en 5 años en el test sintético).

## 5. Limitaciones abiertas

- **Los CSV reales no se han inspeccionado en esta auditoría.** Ninguna afirmación de este informe se refiere a ellos.
- **Semántica exacta de `adj*` y `divCash`:** sin confirmación en la documentación oficial (la web de Tiingo no es accesible desde este entorno). La auditoría supone el ajuste multiplicativo hacia atrás. Si Tiingo usara otro método, la comprobación «Ajustes coherentes con los eventos» fallaría sin que los datos estén mal: habría que revisar el método antes de concluir nada.
- **Los eventos declarados por Tiingo no se contrastan automáticamente con fuentes oficiales.** La auditoría los marca como «no comprobable» y el estado de cada activo nunca sale «OK» mientras falte esa verificación.
- **Interpretación de EXP-001 (no se cambia nada del protocolo):** el efectivo fuera de mercado rinde 0 % y el Sharpe usa una tasa libre de riesgo del 0 %. Entre 2022 y 2025 los tipos fueron altos, así que la estrategia, que pasa tiempo en liquidez, queda en desventaja frente a la realidad. Es un supuesto pre-registrado y debe tenerse en cuenta al leer los resultados, no corregirse.
- El calendario cubre la NYSE. GLD y EFA también cotizan en la NYSE Arca, que sigue los mismos festivos.

## 6. Qué debe ejecutar el usuario en Windows

Desde la carpeta `argos`:

```powershell
git pull
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest                                    # toda la suite
.venv\Scripts\python.exe -m argos.data.audit --salida auditoria.md   # auditoría de los 4 activos
```

En Linux o macOS: los mismos comandos con `.venv/bin/python`.

La auditoría **no ejecuta ninguna estrategia ni descarga nada**. Códigos de salida: `0` sin fallos (puede haber comprobaciones pendientes), `1` si algo falla, `2` si falta algún fichero.

## 7. Comprobaciones que necesitan los CSV reales

1. **Auditoría completa** de SPY, KO, AAPL y XOM con `python -m argos.data.audit`: ningún «fallo».
2. **Calendario:** 4.780 sesiones esperadas; faltan 0 y sobran 0.
3. **Conversión reproducible y original intacto** en los cuatro activos.
4. **Ajustes coherentes con los eventos** en los cuatro activos. Si falla, revisar antes de seguir; puede ser un método de ajuste distinto, no necesariamente un error.
5. **Eventos declarados frente a fuentes oficiales.** Los siguientes son hechos públicos conocidos que **no se han verificado en esta sesión** y que el usuario debe comprobar en las páginas de relación con inversores o en el folleto del ETF:
   - AAPL: split 7:1 (junio de 2014) y 4:1 (agosto de 2020); sin dividendos de 2007 a mediados de 2012.
   - KO: split 2:1 (agosto de 2012).
   - SPY y XOM: sin splits entre 2007 y 2025; dividendos trimestrales.

   Esto permite interpretar el informe que vio el usuario. «Ningún split y cuatro dividendos cada año de 2007 a 2025» es **coherente con SPY o XOM**, pero sería **incoherente con KO** (falta el split de 2012) o **con AAPL** (no pagó dividendos hasta 2012). Hay que identificar de qué activo era ese informe y revisar los cuatro.

## 8. Condiciones antes de autorizar EXP-001

- [ ] `pytest` completo en verde en el PC del usuario.
- [ ] `python -m argos.data.audit` sin ningún «fallo» en los cuatro activos.
- [ ] Eventos corporativos declarados por Tiingo revisados uno a uno frente a fuentes oficiales (punto 7.5), con el resultado anotado.
- [ ] Si «Ajustes coherentes con los eventos» falla en algún activo: explicación documentada antes de continuar.
- [ ] `protocols/EXP-001.json` con huella `7f553e11…98cce` (el ejecutor ya lo comprueba con `LOCKS.json`).
- [ ] Decisión explícita del usuario de ejecutar EXP-001, sin haber visto antes ningún resultado con datos reales.

## Fuentes consultadas (2026-10-08)

- Tiingo, documentación de splits (definición de `splitFactor` y fecha ex): <https://www.tiingo.com/documentation/corporate-actions/splits>
- Tiingo, base de conocimiento (recomendación de volver a descargar todo el histórico tras un evento): <https://www.tiingo.com/kb/article/the-fastest-method-to-ingest-tiingo-end-of-day-stock-api-data/>
- Fuentes secundarias sobre `divCash` y `adj*` (no oficiales): <https://pkg.go.dev/github.com/kenshin579/tiingo-go/eod>, <https://portfoliooptimizer.io/blog/selecting-a-stock-market-data-web-api-not-so-simple/>, <https://www.lean.io/docs/v2/lean-engine/class-reference/classQuantConnect_1_1Data_1_1Custom_1_1Tiingo_1_1TiingoPrice.html>
- Validación del calendario: `pandas_market_calendars` 5.5.0 (instalado solo en un entorno temporal, no es dependencia de ARGOS).
