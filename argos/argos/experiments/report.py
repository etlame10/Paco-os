"""Informe de un experimento, en Markdown.

Reglas de lenguaje (verificadas por tests):
  - Solo frases descriptivas sobre la muestra: "En esta muestra histórica, la
    estrategia obtuvo X frente a Y de Buy & Hold."
  - Nunca "la estrategia funciona", ni recomendaciones de compra o venta.
  - Las conclusiones permitidas y NO permitidas se enumeran explícitamente.
"""

from __future__ import annotations

from argos.experiments.runner import ExperimentResult, PeriodRow

PERIOD_LABEL = {"desarrollo": "Desarrollo", "fuera_de_muestra": "Fuera de muestra"}


def _p(x: float | None, d: int = 1) -> str:
    return "n/d" if x is None else f"{x * 100:+.{d}f}%"


def _u(x: float | None, d: int = 1) -> str:
    return "n/d" if x is None else f"{x * 100:.{d}f}%"


def _n(x: float | None, d: int = 2) -> str:
    return "n/d" if x is None else f"{x:.{d}f}"


def _table(rows: list[PeriodRow]) -> list[str]:
    out = [
        "| Activo | Periodo | Estrategia | Buy & Hold | Diferencia | Drawdown (E / B&H) | Sharpe (E / B&H) | Operaciones |",
        "| ------ | ------- | ---------: | ---------: | ---------: | -----------------: | ---------------: | ----------: |",
    ]
    for r in rows:
        out.append(
            f"| {r.ticker}{'' if r.core else ' *'} | {PERIOD_LABEL.get(r.period_name, r.period_name)} "
            f"({r.start[:4]}–{r.end[:4]}) | {_p(r.strategy_return)} | {_p(r.benchmark_return)} | "
            f"{_p(r.difference)} | {_p(r.strategy_max_dd)} / {_p(r.benchmark_max_dd)} | "
            f"{_n(r.strategy_sharpe)} / {_n(r.benchmark_sharpe)} | {r.n_trades} |"
        )
    return out


def _detail(rows: list[PeriodRow]) -> list[str]:
    out = [
        "| Activo | Periodo | Rent. anual. (E / B&H) | Capital final (E / B&H) | Volatilidad (E / B&H) | Win rate | Mejor op. | Peor op. | Tiempo invertido |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        out.append(
            f"| {r.ticker} | {PERIOD_LABEL.get(r.period_name, r.period_name)} | {_p(r.strategy_cagr)} / {_p(r.benchmark_cagr)} | "
            f"{r.strategy_final:,.0f} / {r.benchmark_final:,.0f} | {_u(r.strategy_vol)} / {_u(r.benchmark_vol)} | "
            f"{'n/d' if r.win_rate is None else f'{r.win_rate:.0%}'} | {_p(r.best_trade)} | {_p(r.worst_trade)} | {r.exposure:.0%} |"
        )
    return out


def _counts(rows: list[PeriodRow], period: str) -> list[str]:
    rs = [r for r in rows if r.period_name == period and r.core]
    if not rs:
        return [f"- {PERIOD_LABEL[period]}: ningún activo principal evaluado."]
    better = [r.ticker for r in rs if r.difference > 0]
    worse = [r.ticker for r in rs if r.difference <= 0]
    dd_less = [r.ticker for r in rs if r.strategy_max_dd > r.benchmark_max_dd]
    dd_more = [r.ticker for r in rs if r.strategy_max_dd <= r.benchmark_max_dd]
    sh_ok = [r for r in rs if r.strategy_sharpe is not None and r.benchmark_sharpe is not None]
    sh_better = [r.ticker for r in sh_ok if r.strategy_sharpe > r.benchmark_sharpe]
    trades = sum(r.n_trades for r in rs)
    j = lambda xs: ", ".join(xs) or "ninguno"  # noqa: E731
    return [
        f"**{PERIOD_LABEL[period]}** ({len(rs)} activos principales, {trades} operaciones en total):",
        f"- Rentabilidad total superior a Buy & Hold en {len(better)} de {len(rs)}: {j(better)}.",
        f"- Rentabilidad total inferior o igual a Buy & Hold en {len(worse)} de {len(rs)}: {j(worse)}.",
        f"- Sharpe superior a Buy & Hold en {len(sh_better)} de {len(sh_ok)}: {j(sh_better)}.",
        f"- Caída máxima menor que Buy & Hold en: {j(dd_less)}.",
        f"- Caída máxima mayor o igual que Buy & Hold en: {j(dd_more)}.",
    ]


def render_markdown(res: ExperimentResult) -> str:
    p = res.protocol
    L: list[str] = []
    a = L.append
    a(f"# {res.experiment_id} · {res.title}")
    a("")
    if res.dry_run:
        a("> ⚠ **ENSAYO CON DATOS SIMULADOS.** Las series son inventadas por ordenador para comprobar el "
          "procedimiento. Estos números **no dicen nada del mercado real** y no son el resultado del experimento.")
        a("")
    a("> **Resultado histórico, no predicción.** Describe lo que habría ocurrido en una muestra del pasado con "
      "reglas fijadas de antemano. No es una recomendación de inversión.")
    a("")
    a(f"- Ejecutado: {res.run_at} · ARGOS {res.argos_version} · commit {res.git_commit or 'n/d'}")
    a(f"- Protocolo: `protocols/{res.experiment_id}.json` (registrado el {p.registered_at}) · SHA-256 `{res.protocol_sha256[:16]}…`")
    a(f"- Estrategia: `{p.strategy['name']}` {p.strategy['params']} · capital {p.costs['initial_capital']:,} · "
      f"comisión {p.costs['commission_pct']:.3%} · slippage {p.costs['slippage_pct']:.3%}")
    a("")
    a("## Hipótesis (fijada antes de los datos)")
    a("")
    for k, v in p.hypothesis.items():
        a(f"- **{k.upper()}**: {v}")
    a("")

    a("## 1-3. Datos utilizados, procedencia y periodo")
    a("")
    a("| Activo | Papel | Estado | Fichero | Procedencia declarada | Cobertura |")
    a("| --- | --- | --- | --- | --- | --- |")
    for s in res.assets:
        q = s.quality
        cov = f"{q.first_date} → {q.last_date} ({q.n_bars} sesiones)" if q else "—"
        src = s.source_note or ("⚠ no documentada (añade `<TICKER>.source.txt`)" if s.status != "sin datos" else "—")
        a(f"| {s.ticker}{'' if s.core else ' *'} | {s.role} | **{s.status}** | {s.data_file or '—'} | {src} | {cov} |")
    a("")
    a("\\* activo complementario (no cuenta para los criterios).")
    a("")
    for s in res.assets:
        if s.status != "evaluado":
            a(f"- **{s.ticker}** — {s.status}: {s.detail}")
    a("")
    a("Periodos fijados en el protocolo:")
    for per in p.periods:
        a(f"- **{PERIOD_LABEL.get(per.name, per.name)}**: {per.start} → {per.end}. {per.note}")
    a(f"- **Reservado (no se mira)**: desde {p.reserved_holdout['start']}. {p.reserved_holdout['note']}")
    a("")

    a("## 4. Controles de calidad")
    a("")
    for s in res.assets:
        if not s.quality:
            continue
        a(f"**{s.ticker}** — {s.quality.summary()}")
        a("")
        for c in s.quality.checks:
            icon = {"ok": "✅", "aviso": "⚠️", "bloqueo": "⛔"}[c.status]
            ex = f" Ejemplos: {'; '.join(c.examples)}." if c.examples else ""
            a(f"- {icon} {c.label}: {c.detail}{ex}")
        if s.data_sha256:
            a(f"- Huella del fichero (SHA-256): `{s.data_sha256}`")
        a("")

    if not res.rows:
        a("## 5-7. Resultados")
        a("")
        a("**No se ha ejecutado ningún backtest**: ningún activo tiene datos válidos. No hay resultados que mostrar "
          "y, por tanto, no se puede sacar ninguna conclusión.")
        a("")
    else:
        a("## 5. Resultados por activo")
        a("")
        L.extend(_table(res.rows))
        a("")
        L.extend(_detail(res.rows))
        a("")
        a("Lectura literal, sin interpretación:")
        a("")
        for r in res.rows:
            a(f"- {r.ticker}, {PERIOD_LABEL.get(r.period_name, r.period_name).lower()} ({r.start} → {r.end}): en esta muestra "
              f"histórica, la estrategia obtuvo {_p(r.strategy_return)} frente a {_p(r.benchmark_return)} de Buy & Hold, "
              f"con una caída máxima de {_p(r.strategy_max_dd)} frente a {_p(r.benchmark_max_dd)}, y {r.n_trades} operación(es).")
        a("")

        a("## 6. Comparación con Buy & Hold (consistencia)")
        a("")
        for per in p.periods:
            L.extend(_counts(res.rows, per.name))
            a("")

        a("## 7. Dentro y fuera de muestra, y por régimen de mercado")
        a("")
        a(f"Clasificación de cada año natural completo (fijada en el protocolo): {p.regime_classification['rule']}")
        a("")
        a("| Periodo | Régimen | Años (activo-año) | Rent. media estrategia | Rent. media Buy & Hold | Años con estrategia mejor |")
        a("| --- | --- | ---: | ---: | ---: | ---: |")
        for name, summ in res.regimes.items():
            for g in summ:
                a(f"| {PERIOD_LABEL.get(name, 'Total')} | {g.regime} | {g.n_years} | {_p(g.mean_strategy_return)} | "
                  f"{_p(g.mean_benchmark_return)} | {g.years_strategy_better} de {g.n_years} |")
        a("")
        a("Incluye los activos complementarios. Los años de un mismo régimen no son independientes entre activos "
          "(p. ej. 2008 o 2022 afectan a todos a la vez).")
        a("")

        a("### Criterios pre-registrados")
        a("")
        for c in res.criteria:
            if c.met is None:
                state = f"NO EVALUABLE (solo {c.total} activo(s) principal(es) con datos válidos)"
            else:
                state = f"{'CUMPLIDO' if c.met else 'NO CUMPLIDO'}: {c.count} de {c.total} (se necesitaban {c.needed})"
            a(f"- **Criterio {c.name}** — {c.text} → **{state}**.")
        a("")
        a(f"_{p.success_criteria['interpretation']}_")
        a("")

    a("## 8. Limitaciones")
    a("")
    oos = [r for r in res.rows if r.period_name == "fuera_de_muestra"]
    min_trades = p.success_criteria["minimum_trades_caveat"]
    n_eval = sum(1 for s in res.assets if s.status == "evaluado")
    if oos:
        per_asset = ", ".join(f"{r.ticker} {r.n_trades}" for r in oos)
        few = [r.ticker for r in oos if r.n_trades < min_trades]
        sample = (f"Muestra pequeña: {n_eval} activo(s) evaluado(s). Operaciones por activo fuera de muestra: "
                  f"{per_asset}. " + (f"En {len(few)} de {len(oos)} activos hay menos de {min_trades} operaciones: "
                  "el resultado de cada activo por separado no tiene base estadística." if few else ""))
    else:
        sample = f"Muestra pequeña: {n_eval} activo(s) evaluado(s) y ninguna operación fuera de muestra."
    lims = [
        sample,
        "Selección de activos con sesgo de supervivencia: se eligieron empresas que existen hoy.",
        "La regla solo actúa en los cruces: al empezar cada periodo está en liquidez hasta el primer cruce, "
        "aunque las medias ya estuvieran en situación alcista. Así se definió y no se cambia.",
        "Costes simplificados: comisión proporcional y slippage fijo. Sin impuestos, sin dividendos en efectivo "
        "(salvo que los precios estén ajustados), sin interés del efectivo mientras se está fuera del mercado.",
        "Los años del mismo régimen se solapan entre activos: no son observaciones independientes.",
        "ARGOS no puede verificar el origen ni el ajuste por dividendos de los ficheros aportados.",
    ]
    if res.dry_run:
        lims.insert(0, "ENSAYO: los datos son simulados. Nada de este informe se aplica al mercado real.")
    for x in lims:
        a(f"- {x}")
    a("")

    a("## 9. Qué conclusiones PODEMOS sacar")
    a("")
    if res.dry_run:
        a("- Que el procedimiento completo (datos → control de calidad → backtest → registro → informe) se ejecuta de "
          "principio a fin. Nada más.")
    elif not res.rows:
        a("- Ninguna sobre la estrategia: no se ha podido ejecutar el experimento por falta de datos válidos.")
    else:
        a("- Qué ocurrió en ESTA muestra concreta, con ESTAS reglas y ESTOS costes (secciones 5-7).")
        a("- Si en esta muestra se cumplieron o no los criterios fijados de antemano.")
        a("- Si el comportamiento fue similar o distinto entre desarrollo y fuera de muestra.")
    a("")
    a("## 10. Qué conclusiones NO podemos sacar")
    a("")
    for x in [
        "Que la estrategia vaya a comportarse igual en el futuro.",
        "Que la estrategia sea buena o mala en general: es un único experimento con pocos activos y pocas operaciones.",
        "Ninguna recomendación de comprar, vender o mantener ningún activo.",
        "Que otros parámetros funcionarían mejor: este experimento no compara parámetros, y hacerlo a partir de "
        "estos resultados sería ajustar la regla a la muestra (sobreajuste).",
        "Nada sobre activos o periodos que no están en la muestra.",
    ]:
        a(f"- {x}")
    a("")
    a("---")
    a("_Siguiente paso: decidir el próximo experimento con un protocolo NUEVO, escrito antes de ver sus datos._")
    return "\n".join(L) + "\n"
