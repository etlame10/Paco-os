# Cómo experimenta ARGOS

**HIPÓTESIS → DATOS → EXPERIMENTO → RESULTADOS → VALIDACIÓN → CONCLUSIÓN**

Nunca: *resultado → buscar una explicación que lo justifique.*

## Reglas

1. **El protocolo se escribe antes que los datos.** `protocols/EXP-XXX.json` fija la hipótesis, la estrategia y sus parámetros, los costes, los activos, los periodos, la clasificación de regímenes y los criterios de éxito. Se sube a git **antes** de ejecutar nada: el historial demuestra el orden.
2. **El protocolo no se toca después de ver resultados.** ARGOS guarda la huella SHA-256 del protocolo con cada resultado real y **se niega a ejecutar** un protocolo modificado. Para cambiar algo hay que crear un experimento nuevo.
3. **Separación temporal.** Periodo de desarrollo y periodo fuera de muestra. Los criterios se evalúan fuera de muestra. Una parte final (2026 en EXP-001) se reserva y no se mira.
4. **Siempre contra Buy & Hold**, con el mismo capital, costes y periodo.
5. **Consistencia antes que éxito puntual.** Se cuenta en cuántos activos mejora o empeora y en qué regímenes, no si un activo dio un buen resultado.
6. **Lenguaje descriptivo.** "En esta muestra histórica, la estrategia obtuvo X frente a Y de Buy & Hold." Nunca "la estrategia funciona", ni recomendaciones. Hay tests que lo verifican.
7. **Nada se oculta.** Activos sin datos, datos bloqueados por calidad y criterios no evaluables aparecen en el informe.
8. **Ensayos ≠ resultados.** Los ensayos con datos simulados quedan marcados como `ENSAYO` en el registro y en el informe, y nunca cuentan.
9. **Sin optimización a posteriori.** Probar variantes de parámetros a la vista de los resultados es sobreajuste. Si alguna vez se compara parámetros, será un experimento propio, pre-registrado, con su propia validación fuera de muestra.

## Registro de experimentos

`data/experiments/registry.jsonl` (local; una línea JSON por backtest, solo se añaden líneas). Cada línea guarda:

- fecha, versión de ARGOS y commit de git;
- experimento, huella del protocolo y periodo;
- activo, origen y SHA-256 del fichero de datos, y resultado del control de calidad;
- estrategia, parámetros, capital, comisión y slippage;
- todas las métricas de la estrategia y de Buy & Hold, la diferencia, la auditoría anti look-ahead y el veredicto.

Se puede consultar en la pestaña Backtest de la interfaz (sección «Registro de experimentos») o en `GET /api/experiments`. Desde la interfaz también se puede guardar un backtest suelto: el servidor lo vuelve a ejecutar y nunca guarda métricas enviadas por el navegador.

## Experimentos

| Id | Pregunta | Estado |
| --- | --- | --- |
| EXP-001 | ¿Aporta el cruce 50/200 algo frente a Buy & Hold en datos reales? | Pre-registrado. **Pendiente de datos reales.** |
