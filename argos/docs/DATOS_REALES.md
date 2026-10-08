# Datos reales para el experimento EXP-001

ARGOS **no descarga datos**. Tú los consigues de una fuente fiable, los dejas en `data/csv/` y ARGOS los comprueba antes de usarlos. Si algo no cuadra, avisa o se niega a continuar; nunca rellena ni corrige.

## 1. Qué histórico necesitamos (explicado sencillo)

Para cada activo, una tabla con **una fila por día de mercado** desde **enero de 2007** hasta **el 31 de diciembre de 2025**. Cada fila tiene el precio de apertura, el máximo, el mínimo, el cierre y el volumen de ese día.

- **¿Por qué desde 2007?** Las reglas se evalúan desde 2008, pero la media de 200 sesiones necesita casi un año de datos previos para poder calcularse.
- **¿Por qué hasta 2025?** Es el final del periodo fuera de muestra. 2026 queda reservado para una validación futura y **no se mira**.
- **Precios ajustados.** Si la acción tuvo un *split* o repartió dividendos, los precios antiguos deben estar ajustados. Si no lo están, ARGOS vería una "caída" falsa el día del split y la contaría como pérdida.

## 1 bis. Fuente elegida: Tiingo

Tiingo da, por una vía oficial y repetible, las cuatro columnas de precio **ajustadas por splits y dividendos** (`adjOpen`, `adjHigh`, `adjLow`, `adjClose`) y además indica cada split (`splitFactor`) y cada dividendo (`divCash`). Plan gratuito con clave personal; licencia de **uso personal** (no publiques los datos).

### Cadena completa

```
Tiingo ──► data/raw/tiingo/  (original intacto + manifest.jsonl con fecha y SHA-256)
       ──► data/csv/<TICKER>.csv + <TICKER>.source.txt   (conversión mecánica)
       ──► control de integridad con los requisitos de EXP-001
```

- **Activos y fechas** se leen del protocolo (solo lectura): SPY, KO, AAPL, XOM · 2007-01-01 → 2025-12-31. No se pueden cambiar desde la línea de comandos.
- **La clave** se lee **solo** de la variable de entorno `TIINGO_API_KEY`, viaja en la cabecera HTTP (no en la URL) y nunca se escribe en ningún fichero ni se muestra en pantalla. Si falta, el programa se detiene.
- **Los originales** se guardan byte a byte, con un nombre único que incluye la fecha de descarga; nunca se sobrescriben. Su SHA-256 queda en `data/raw/tiingo/manifest.jsonl`.
- **Antes de guardar** se valida la respuesta: errores de autenticación, ticker desconocido, límite de peticiones, respuestas vacías, mensajes en lugar de CSV, columnas que faltan, filas cortadas, valores vacíos o no numéricos, fechas mal formadas, duplicadas, desordenadas o fuera de rango, y filas cuyas cuatro columnas ajustadas no usan el mismo factor. En todos esos casos se detiene **sin guardar nada**.
- **La conversión** comprueba primero que el original no ha cambiado (SHA-256) y copia literalmente el texto de `adjOpen, adjHigh, adjLow, adjClose, adjVolume` como `open, high, low, close, volume`. Solo normaliza la fecha a `AAAA-MM-DD`. No redondea, no calcula y no rellena nada. No sobrescribe un CSV distinto sin `--sobrescribir`.
- El `.source.txt` resume la procedencia, las dos huellas, el método y los splits y dividendos que declara Tiingo, para revisarlos.

### Configurar la clave en Windows

1. Crea una cuenta gratuita en tiingo.com y copia tu *API token* (en tu perfil, apartado API).
2. Guárdala como variable de entorno **de tu usuario** (no se guarda en ARGOS ni en git):
   - **Recomendado (sin dejar rastro en el historial de comandos):** menú Inicio → escribe «variables de entorno» → *Editar las variables de entorno de esta cuenta* → *Nueva…* → Nombre `TIINGO_API_KEY`, Valor: tu clave → Aceptar. Después **cierra y vuelve a abrir** la terminal.
   - **Solo para la ventana actual de PowerShell**, pidiendo la clave sin que quede en el historial:
     ```powershell
     $env:TIINGO_API_KEY = Read-Host "Clave de Tiingo"
     ```
   - Evita `setx TIINGO_API_KEY tu_clave`: funciona, pero la clave queda escrita en el historial de PowerShell.
3. Comprueba que existe sin mostrarla:
   ```powershell
   if ($env:TIINGO_API_KEY) { "TIINGO_API_KEY configurada" } else { "Falta TIINGO_API_KEY" }
   ```

### Descargar, convertir y validar (en tu ordenador)

Desde la carpeta `argos` del proyecto, en PowerShell:

```powershell
py -m venv .venv                       # solo la primera vez
.venv\Scripts\activate
pip install -r requirements-dev.txt    # solo la primera vez

python -m argos.tools.tiingo descargar     # 1. originales a data\raw\tiingo\
python -m argos.tools.tiingo convertir     # 2. CSV de ARGOS + control de integridad de EXP-001
```

`descargar` termina con código 0 si los cuatro activos se descargaron y validaron. Ante un error de autenticación se detiene sin seguir con el resto. `convertir` termina con código 0 solo si los cuatro CSV superan el control de integridad del protocolo.

### Auditar los CSV antes de EXP-001

```powershell
.venv\Scripts\python.exe -m argos.data.audit --salida auditoria.md
```

No ejecuta ninguna estrategia ni descarga nada. Para cada activo comprueba: huella, valores, orden, coherencia OHLC, **sesiones frente al calendario de la NYSE** (distingue festivos de huecos reales), precios repetidos, saltos, procedencia, que el original esté intacto, que la conversión sea reproducible byte a byte y que **los ajustes de Tiingo cuadren con los splits y dividendos que declara**. Detalles y condiciones para autorizar EXP-001: [AUDITORIA_EXP-001.md](AUDITORIA_EXP-001.md).

> «Sin splits sin ajustar» en el control de calidad **no** significa que no hubiera splits: en una serie ajustada los splits no producen saltos. Los splits declarados aparecen en el `.source.txt` y en la auditoría.

### Si aparece `CERTIFICATE_VERIFY_FAILED` (por ejemplo, «certificate has expired»)

ARGOS verifica siempre el certificado de Tiingo y **nunca** se conecta sin verificar. Usa las autoridades de confianza del paquete `certifi` (lista de Mozilla, versión fijada en `requirements.txt`) en lugar del almacén de Windows, que Python no actualiza automáticamente.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt     # instala/actualiza certifi
.venv\Scripts\python.exe -m argos.tools.tiingo diagnosticar-tls  # solo prueba la conexión: sin clave, sin datos
```

El diagnóstico muestra la hora de tu PC, compara la confianza de `certifi` con la de Windows y da una conclusión:
- **Falla con ambas** → revisa primero la fecha y hora (Configuración → Hora e idioma → Sincronizar ahora).
- **Solo funciona con Windows** → probablemente un antivirus o proxy inspecciona HTTPS con su propio certificado; revisa la opción de «análisis HTTPS» o «escaneo de conexiones cifradas».
- **Funciona con `certifi`** → ya puedes ejecutar `descargar`.

> El entorno en la nube donde se desarrolló ARGOS no tiene acceso de red a Tiingo, y de todos modos es mejor que tu clave no salga de tu ordenador: ejecuta la descarga en tu PC.

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

(No es necesario con Tiingo: su conversor ya usa las columnas ajustadas.) Multiplica apertura, máximo y mínimo por `Adj Close / Close`, usa `Adj Close` como cierre y lo anota en `KO.source.txt`. No rellena nada: si una fila está incompleta (por ejemplo `null`), se detiene e indica la línea.

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
