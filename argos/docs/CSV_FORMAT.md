# Cómo introducir un histórico real en CSV

ARGOS **no descarga datos**. Tú consigues el histórico (exportación de tu bróker, de una web de datos financieros, etc.) y lo dejas en una carpeta. ARGOS lo lee, lo valida y lo usa para analizar y hacer backtesting.

## 1. Dónde y con qué nombre

```
argos/data/csv/<TICKER>.csv
```

- El **nombre del fichero es el ticker**, en mayúsculas: `AAPL.csv`, `SPY.csv`, `SAN.MC.csv`, `BTC-USD.csv`.
  - Caracteres permitidos: letras, números, `.`, `-`, `^`, `=`. Máximo 20.
- Al recargar la página aparecerá en la lista de tickers (sin la etiqueta "demo").
- La carpeta está en `.gitignore`: **tus datos no se suben al repositorio**.
- Puedes usar otra carpeta definiendo la variable de entorno `ARGOS_CSV_DIR`.
- ⚠ Los ficheros cuyo nombre empieza por `DEMO-` se tratan **siempre como datos simulados**. No uses ese prefijo para datos reales.

## 2. Contenido exacto

```csv
date,open,high,low,close,volume
2024-01-02,187.15,188.44,183.89,185.64,82488700
2024-01-03,184.22,185.88,183.43,184.25,58414500
```

*(Las cifras de arriba son solo ilustrativas del formato.)*

| Columna | Obligatoria | Formato | Notas |
| --- | --- | --- | --- |
| `date` | ✅ | `AAAA-MM-DD` | Se admite `AAAA-MM-DD 00:00:00`. Cualquier otra hora → rechazado (intradía). |
| `open` | ✅ | número con **punto** decimal | Precio de apertura. |
| `high` | ✅ | número | Máximo de la sesión. |
| `low` | ✅ | número | Mínimo de la sesión. |
| `close` | ✅ | número | Cierre. Se usa para indicadores, señales y valoración. |
| `volume` | ✅ | número (entero o decimal) | Si la fuente no tiene volumen, escribe `0` explícitamente; una celda vacía se rechaza. |

Reglas:

- **Separador de campos: coma** (`,`). El punto y coma (`;`, típico de Excel en español) se rechaza con un aviso.
- **Separador decimal: punto** (`185.64`). No uses separador de miles (`1,234.56` o `1.234,56` se rechazan).
- Codificación UTF-8 (con o sin BOM).
- Nombres de columna sin distinguir mayúsculas (`Date`, `Close`… valen). Las columnas extra se ignoran (por ejemplo `Adj Close`).
- El orden de las filas da igual: ARGOS las ordena por fecha.

## 3. Frecuencia

**Solo datos DIARIOS** (una fila por sesión). ARGOS rechaza:

- Datos intradía (filas con hora).
- Fechas repetidas.
- Datos semanales o mensuales (si la separación típica entre filas supera 4 días).

Los fines de semana y festivos simplemente no aparecen; no hay que rellenarlos. Las criptomonedas, que cotizan todos los días, también son válidas.

## 4. Qué hace ARGOS con tus datos (y qué no)

| Situación | Qué ocurre |
| --- | --- |
| Fecha mal escrita, inexistente (2024-02-30), anterior a 1900 o futura | ❌ Rechaza el fichero indicando la línea |
| Precio vacío, no numérico, `nan`, `inf` | ❌ Rechaza el fichero indicando la línea y la columna |
| Fichero sin filas | ❌ "no contiene ninguna fila de datos" |
| Máximo/mínimo incoherente con apertura/cierre, precio ≤ 0 | ⚠ Descarta esa sesión y lo anota en "Notas de normalización" |
| Salto de cierre > 40 % en un día | ⚠ Lo conserva y avisa: posible split no ajustado o error |

ARGOS **nunca rellena, interpola ni corrige** valores.

## 5. Precios ajustados (importante para backtesting)

Si la acción tuvo un *split* (p. ej. 4 por 1), los precios **sin ajustar** mostrarán una caída falsa del 75 % ese día, y el backtest la contaría como una pérdida real. Por eso:

- Usa precios **ajustados por splits** (y, si puedes, por dividendos).
- Si tu fuente da `Close` y `Adj Close` por separado, lo más coherente es que **las cuatro columnas** (`open`, `high`, `low`, `close`) estén ajustadas. Si solo tienes `Adj Close`, no lo mezcles con un `open` sin ajustar: el precio de ejecución (apertura) y el de valoración (cierre) quedarían en escalas distintas.

## 6. Cuántos datos hacen falta

- Análisis: al menos 60 sesiones (200 para la media de 200).
- Backtest de cruce de medias 50/200: al menos **202 sesiones** antes del final del periodo, y conviene **varios años** (más de 1.000 sesiones) para que haya suficientes cruces.

## 7. Probar con el ejemplo

`data/examples/DEMO-EJEMPLO.csv` es un fichero de ejemplo con datos **SIMULADOS** (activo ficticio). Sirve para ver el formato y para probar la importación:

```bash
cp data/examples/DEMO-EJEMPLO.csv data/csv/
```

Aparecerá como `DEMO-EJEMPLO` marcado como datos de demostración.
