// ARGOS — sección BACKTEST. Reutiliza los helpers de app.js ($, el, nf).
// Solo lee de /api/backtest*. Nada aquí ejecuta operaciones.
"use strict";

const BT_COLORS = { argos: "#2ba489", bh: "#9b7af0", price: "#a3aec2", entry: "#3ddc97", exit: "#ff6b6b" };
const pctFmt = (x, d = 2) => (x === null || x === undefined ? "n/d" : `${x > 0 ? "+" : ""}${nf(d).format(x * 100)} %`);
const money = (x) => (x === null || x === undefined ? "n/d" : `${nf(2).format(x)}`);
const num2 = (x) => (x === null || x === undefined ? "n/d" : nf(2).format(x));
let btOptions = null;

// ------------------------------------------------------------- pestañas

function showView(view) {
  for (const btn of document.querySelectorAll(".tab")) {
    const on = btn.dataset.view === view;
    btn.classList.toggle("active", on);
    if (on) btn.setAttribute("aria-current", "page"); else btn.removeAttribute("aria-current");
  }
  $("view-analysis").hidden = view !== "analysis";
  $("view-backtest").hidden = view !== "backtest";
  if (view === "backtest" && !btOptions) loadBacktestOptions();
}
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));

// ------------------------------------------------------------- formulario

async function loadBacktestOptions() {
  try {
    btOptions = await (await fetch("/api/backtest/options")).json();
  } catch {
    showBtError("No se pudo contactar con el servidor de ARGOS.");
    return;
  }
  const tSel = $("bt-ticker");
  tSel.replaceChildren(...btOptions.tickers.map((t) =>
    el("option", { value: t.ticker, text: `${t.ticker}${t.is_simulated ? " · demo (simulado)" : " · CSV real"}` })));
  const sSel = $("bt-strategy");
  sSel.replaceChildren(...btOptions.strategies.map((s) => el("option", { value: s.name, text: s.label })));
  sSel.addEventListener("change", renderParamInputs);
  renderParamInputs();
}

function renderParamInputs() {
  const s = btOptions.strategies.find((x) => x.name === $("bt-strategy").value);
  $("bt-strategy-desc").textContent = s ? s.description : "";
  $("bt-params").replaceChildren(...Object.entries(s ? s.params : {}).map(([key, spec]) =>
    el("label", {}, spec.description,
      el("input", { type: "number", "data-param": key, min: spec.min, max: spec.max, step: 1, value: spec.default, required: true }))));
}

function showBtError(msg) {
  $("bt-results").hidden = true;
  $("bt-demo-banner").hidden = true;
  $("bt-error").textContent = msg;
  $("bt-error").hidden = false;
}

$("bt-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = new URLSearchParams({
    ticker: $("bt-ticker").value,
    strategy: $("bt-strategy").value,
    capital: $("bt-capital").value,
    commission_percent: $("bt-commission").value,
    slippage_percent: $("bt-slippage").value,
  });
  if ($("bt-start").value) q.set("start", $("bt-start").value);
  if ($("bt-end").value) q.set("end", $("bt-end").value);
  document.querySelectorAll("#bt-params input").forEach((i) => q.set(i.dataset.param, i.value));

  const btn = $("bt-run");
  btn.disabled = true;
  btn.textContent = "Simulando…";
  $("bt-error").hidden = true;
  try {
    const res = await fetch(`/api/backtest?${q}`);
    const body = await res.json();
    if (!res.ok) {
      const d = body.detail;
      throw new Error(Array.isArray(d) ? d.map((x) => `${(x.loc || []).slice(-1)[0]}: ${x.msg}`).join(" · ") : d || `Error ${res.status}`);
    }
    renderBacktest(body);
  } catch (err) {
    showBtError(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Ejecutar backtest";
  }
});

// ------------------------------------------------------------- render

function renderBacktest(r) {
  $("bt-demo-banner").hidden = !r.is_simulated_data;
  $("bt-demo-text").textContent = r.transparency.data.warning || "";
  $("bt-warning").textContent = r.warning;
  renderSummary(r);
  renderComparison(r);
  renderBtChart(r);
  renderTrades(r);
  renderTransparency(r);
  $("bt-results").hidden = false;
}

const tile = (label, value, sub) =>
  el("div", { class: "tile" }, el("span", { class: "tile-label", text: label }), el("span", { class: "tile-value", text: value }), sub ? el("span", { class: "tile-sub", text: sub }) : null);

function renderSummary(r) {
  const m = r.strategy.metrics;
  $("bt-summary").replaceChildren(
    el("p", { class: "interp-detail" }, el("b", { text: `${r.strategy.label} · ${r.ticker}` }),
      ` · ${r.transparency.period.start} → ${r.transparency.period.end}`),
    el("div", { class: "tiles" },
      tile("Capital inicial", money(m.initial_capital)),
      tile("Capital final", money(m.final_capital)),
      tile("Rentabilidad", pctFmt(m.total_return), m.annualized_return !== null ? `${pctFmt(m.annualized_return)} anual` : "no anualizada"),
      tile("Caída máxima", pctFmt(m.max_drawdown)),
      tile("Operaciones", String(m.n_trades)),
      tile("Win rate", m.win_rate === null ? "n/d" : pctFmt(m.win_rate, 0).replace("+", "")),
    ),
    ...r.notes.map((n) => el("p", { class: "status-note", text: n })),
  );
}

function renderComparison(r) {
  const s = r.strategy.metrics, b = r.benchmark.metrics;
  const rows = [
    ["Capital final", money(s.final_capital), money(b.final_capital), money(s.final_capital - b.final_capital)],
    ["Rentabilidad total", pctFmt(s.total_return), pctFmt(b.total_return), `${pctFmt(s.total_return - b.total_return)} (puntos)`],
    ["Rentabilidad anualizada", pctFmt(s.annualized_return), pctFmt(b.annualized_return), s.annualized_return === null || b.annualized_return === null ? "n/d" : pctFmt(s.annualized_return - b.annualized_return)],
    ["Caída máxima", pctFmt(s.max_drawdown), pctFmt(b.max_drawdown), pctFmt(s.max_drawdown - b.max_drawdown)],
    ["Volatilidad anualizada", pctFmt(s.volatility), pctFmt(b.volatility), s.volatility === null || b.volatility === null ? "n/d" : pctFmt(s.volatility - b.volatility)],
    ["Sharpe", num2(s.sharpe), num2(b.sharpe), s.sharpe === null || b.sharpe === null ? "n/d" : num2(s.sharpe - b.sharpe)],
    ["Operaciones", String(s.n_trades), String(b.n_trades), ""],
    ["Win rate", s.win_rate === null ? "n/d" : pctFmt(s.win_rate, 0), b.win_rate === null ? "n/d" : pctFmt(b.win_rate, 0), ""],
    ["Beneficio medio por operación", s.avg_trade_pnl === null ? "n/d" : `${money(s.avg_trade_pnl)} (${pctFmt(s.avg_trade_return)})`, b.avg_trade_pnl === null ? "n/d" : `${money(b.avg_trade_pnl)} (${pctFmt(b.avg_trade_return)})`, ""],
    ["Mejor operación", pctFmt(s.best_trade_return), pctFmt(b.best_trade_return), ""],
    ["Peor operación", pctFmt(s.worst_trade_return), pctFmt(b.worst_trade_return), ""],
    ["Tiempo invertido", pctFmt(s.exposure, 0).replace("+", ""), pctFmt(b.exposure, 0).replace("+", ""), ""],
    ["Costes pagados (comisión + slippage)", money(s.total_costs), money(b.total_costs), ""],
  ];
  const itemsByMetric = Object.fromEntries(r.comparison.items.map((i) => [i.metric, i]));
  const mark = (label) => {
    const key = { "Rentabilidad total": "total_return", "Caída máxima": "max_drawdown", "Volatilidad anualizada": "volatility", Sharpe: "sharpe" }[label];
    const it = key && itemsByMetric[key];
    if (!it || it.better === null) return null;
    return el("span", { class: `stance ${it.better ? "stance-alcista" : "stance-bajista"}`, text: it.better ? "ARGOS mejor" : "B&H mejor" });
  };
  $("bt-comparison").replaceChildren(
    el("p", { class: "verdict", text: r.comparison.verdict }),
    el("table", { class: "factors cmp" },
      el("thead", {}, el("tr", {}, ["Métrica", "ARGOS", "Buy & Hold", "Diferencia", ""].map((h) => el("th", { text: h })))),
      el("tbody", {}, rows.map(([label, a, bh, diff]) =>
        el("tr", {}, el("td", { text: label }), el("td", { class: "num", text: a }), el("td", { class: "num", text: bh }), el("td", { class: "num", text: diff }), el("td", {}, mark(label)))))),
    el("p", { class: "interp-detail" }, el("b", { text: "Sharpe: " }), r.strategy.metrics.sharpe_note),
    el("h3", { text: "Antes de sacar conclusiones" }),
    el("ul", { class: "caveats" }, r.comparison.caveats.map((c) => el("li", { text: c }))),
  );
}

function renderTrades(r) {
  const trades = r.strategy.simulation.trades;
  const ignored = r.strategy.simulation.ignored_signals;
  const body = trades.length
    ? el("table", { class: "factors" },
      el("thead", {}, el("tr", {}, ["#", "Señal", "Entrada", "Precio entrada", "Señal", "Salida", "Precio salida", "Resultado", "%", "Motivo salida"].map((h) => el("th", { text: h })))),
      el("tbody", {}, trades.map((t, i) => el("tr", {},
        el("td", { text: String(i + 1) }),
        el("td", { class: "num muted", text: t.entry_signal_date }),
        el("td", { class: "num", text: t.entry_date }),
        el("td", { class: "num", text: num2(t.entry_price), title: `Apertura ${num2(t.entry_reference_price)} + slippage` }),
        el("td", { class: "num muted", text: t.exit_signal_date || "—" }),
        el("td", { class: "num", text: t.exit_date }),
        el("td", { class: "num", text: num2(t.exit_price), title: `Referencia ${num2(t.exit_reference_price)} − slippage` }),
        el("td", { class: `num ${t.pnl >= 0 ? "pos" : "neg"}`, text: money(t.pnl) }),
        el("td", { class: `num ${t.pnl >= 0 ? "pos" : "neg"}`, text: pctFmt(t.return_pct) }),
        el("td", { class: "muted", text: t.exit_reason }),
      ))))
    : el("p", { class: "status-note", text: "La estrategia no realizó ninguna operación en este periodo." });
  $("bt-trades").replaceChildren(...[
    el("p", { class: "interp-detail", text: "Precios efectivos, ya con slippage. Resultado neto de comisiones. «Señal» es la sesión en que se calculó; la ejecución es en la apertura siguiente." }),
    el("div", { class: "table-scroll" }, body),
    ignored.length ? el("h3", { text: "Señales no ejecutadas" }) : null,
    ignored.length ? el("ul", { class: "caveats" }, ignored.map((g) => el("li", { text: `${g.signal.date} · ${g.signal.action}: ${g.reason}` }))) : null,
  ].filter(Boolean));
}

function renderTransparency(r) {
  const t = r.transparency, d = t.data;
  const params = Object.entries(t.strategy.params).map(([k, v]) => `${k} = ${v}`).join(", ") || "sin parámetros";
  const rows = [
    ["Datos utilizados", `${d.ticker} · ${d.source} (proveedor «${d.provider}») · ${d.is_simulated ? "SIMULADOS" : "reales importados"} · frecuencia ${d.frequency}`],
    ["Disponibles", `${d.available_from} → ${d.available_to}`],
    ["Sesiones", `${d.bars_in_period} en el periodo · ${d.bars_used_by_strategy} vistas por la estrategia (incluye historia previa para calentar indicadores)`],
    ["Estrategia", `${t.strategy.label} — ${t.strategy.description}`],
    ["Parámetros", `${params} · necesita ${t.strategy.min_bars} sesiones antes de su primera señal`],
    ["Comisiones", t.commission],
    ["Slippage", t.slippage],
    ["Periodo", `${t.period.start} → ${t.period.end}`],
    ["Ejecución", t.execution_rule],
    ["Tamaño de posición", t.position_sizing],
    ["Precios", d.price_used],
    ["Anti look-ahead", `${r.lookahead_audit.passed ? "SUPERADA" : "FALLIDA"} · ${r.lookahead_audit.checked_cutoffs} cortes comprobados. ${r.lookahead_audit.method}`],
  ];
  $("bt-transparency").replaceChildren(
    el("table", { class: "kv transp" }, el("tbody", {}, rows.map(([k, v]) => el("tr", {}, el("td", { text: k }), el("td", { text: v }))))),
    el("h3", { text: "Supuestos" }),
    el("ul", { class: "caveats" }, t.assumptions.map((a) => el("li", { text: a }))),
    el("div", { class: "disclaimer-box", text: r.warning }),
  );
}

// ------------------------------------------------------------- gráfico

function renderBtChart(r) {
  const NS = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };
  const pts = r.strategy.simulation.equity_curve;
  const bh = r.benchmark.simulation.equity_curve;
  const n = pts.length;
  const W = 760, L = 8, R = 92, H1 = 200, H2 = 170, GAP = 26, T = 10;
  const x = (i) => L + (i / Math.max(1, n - 1)) * (W - L - R);
  const scale = (vals, top, h) => {
    const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * 0.06 || 1;
    return { y: (v) => top + h - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * h, lo, hi };
  };
  const closes = pts.map((p) => p.close);
  const sp = scale(closes, T, H1);
  const top2 = T + H1 + GAP;
  const se = scale([...pts.map((p) => p.equity), ...bh.map((p) => p.equity)], top2, H2);
  const line = (vals, y) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");

  const svg = mk("svg", { viewBox: `0 0 ${W} ${top2 + H2 + 22}`, class: "chart bt-chart", role: "img",
    "aria-label": "Precio con entradas y salidas, y evolución del capital de la estrategia frente a Buy & Hold" });
  const grid = (top, h, s, fmt) => {
    for (const f of [0, 0.5, 1]) {
      const v = s.lo + (s.hi - s.lo) * f, yy = s.y(v);
      svg.append(mk("line", { x1: L, x2: W - R, y1: yy, y2: yy, class: "grid-line" }));
      const t = mk("text", { x: W - R + 6, y: yy + 4, class: "axis-label" }); t.textContent = fmt(v); svg.append(t);
    }
  };
  const title = (txt, yy) => { const t = mk("text", { x: L, y: yy, class: "panel-label" }); t.textContent = txt; svg.append(t); };
  grid(T, H1, sp, (v) => nf(2).format(v));
  grid(top2, H2, se, (v) => nf(0).format(v));
  title("Precio de cierre · ▲ entrada · ▼ salida", T + 10);
  title("Capital", top2 + 10);

  svg.append(mk("path", { d: line(closes, sp.y), fill: "none", stroke: BT_COLORS.price, "stroke-width": 1.5 }));
  svg.append(mk("path", { d: line(bh.map((p) => p.equity), se.y), fill: "none", stroke: BT_COLORS.bh, "stroke-width": 2 }));
  svg.append(mk("path", { d: line(pts.map((p) => p.equity), se.y), fill: "none", stroke: BT_COLORS.argos, "stroke-width": 2 }));

  // Etiquetas directas al final de cada línea de capital (identidad no solo por color).
  const endLabel = (txt, v, color, dy) => {
    const t = mk("text", { x: W - R + 6, y: se.y(v) + dy, class: "series-label" }); t.textContent = txt;
    const k = mk("line", { x1: W - R - 2, x2: W - R + 3, y1: se.y(v), y2: se.y(v), stroke: color, "stroke-width": 2 });
    svg.append(k, t);
  };
  const lastA = pts[n - 1].equity, lastB = bh[n - 1].equity;
  const sep = Math.abs(se.y(lastA) - se.y(lastB)) < 14 ? 7 : 0;
  endLabel("ARGOS", lastA, BT_COLORS.argos, lastA >= lastB ? -sep : sep + 4);
  endLabel("B&H", lastB, BT_COLORS.bh, lastB > lastA ? -sep : sep + 4);

  // Marcadores de operaciones en el panel de precio (forma + color; sobre un anillo del color de fondo).
  const idx = Object.fromEntries(pts.map((p, i) => [p.date, i]));
  const tri = (i, price, up) => {
    const cx = x(i), cy = sp.y(price), s = 6;
    const d = up ? `M${cx},${cy - s} L${cx + s},${cy + s} L${cx - s},${cy + s}Z` : `M${cx},${cy + s} L${cx + s},${cy - s} L${cx - s},${cy - s}Z`;
    svg.append(mk("path", { d, fill: up ? BT_COLORS.entry : BT_COLORS.exit, stroke: "#141b2b", "stroke-width": 2 }));
  };
  for (const t of r.strategy.simulation.trades) {
    if (idx[t.entry_date] !== undefined) tri(idx[t.entry_date], t.entry_price, true);
    if (idx[t.exit_date] !== undefined) tri(idx[t.exit_date], t.exit_price, false);
  }

  // Capa de interacción: línea vertical + tooltip con todos los valores de esa fecha.
  const cross = mk("line", { x1: 0, x2: 0, y1: T, y2: top2 + H2, class: "crosshair", visibility: "hidden" });
  const hit = mk("rect", { x: L, y: T, width: W - L - R, height: top2 + H2 - T, fill: "transparent", tabindex: 0 });
  svg.append(cross, hit);
  const wrap = el("div", { class: "chart-wrap" });
  const tip = el("div", { class: "chart-tip", role: "status" });
  tip.hidden = true;
  const showAt = (i) => {
    i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    const trade = r.strategy.simulation.trades.find((t) => t.entry_date === pts[i].date || t.exit_date === pts[i].date);
    tip.replaceChildren(...[
      el("div", { class: "tip-date", text: pts[i].date }),
      el("div", {}, el("b", { text: num2(pts[i].close) }), " cierre"),
      el("div", {}, el("i", { class: "key key-argos" }), el("b", { text: money(pts[i].equity) }), " ARGOS"),
      el("div", {}, el("i", { class: "key key-bh" }), el("b", { text: money(bh[i].equity) }), " Buy & Hold"),
      trade ? el("div", { class: "tip-trade", text: trade.entry_date === pts[i].date ? `▲ entrada a ${num2(trade.entry_price)}` : `▼ salida a ${num2(trade.exit_price)}` }) : null,
    ].filter(Boolean));
    tip.hidden = false;
    const rect = svg.getBoundingClientRect();
    const px = (x(i) / W) * rect.width;
    tip.style.left = `${Math.min(px + 12, rect.width - 170)}px`;
    tip.style.top = "8px";
  };
  let cur = n - 1;
  hit.addEventListener("pointermove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const vx = ((ev.clientX - rect.left) / rect.width) * W;
    cur = Math.round(((vx - L) / (W - L - R)) * (n - 1));
    showAt(cur);
  });
  hit.addEventListener("pointerleave", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });
  hit.addEventListener("focus", () => showAt(cur));
  hit.addEventListener("blur", () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); });
  hit.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowLeft") { cur = Math.max(0, cur - 1); showAt(cur); ev.preventDefault(); }
    if (ev.key === "ArrowRight") { cur = Math.min(n - 1, cur + 1); showAt(cur); ev.preventDefault(); }
  });
  wrap.append(svg, tip);

  const swatch = (cls) => el("i", { class: `key ${cls}` });
  const legend = el("div", { class: "chart-legend" },
    el("span", {}, swatch("key-price"), "Precio de cierre"),
    el("span", {}, el("span", { class: "tri-up", text: "▲" }), " Entrada (precio efectivo)"),
    el("span", {}, el("span", { class: "tri-down", text: "▼" }), " Salida (precio efectivo)"),
    el("span", {}, swatch("key-argos"), "Capital ARGOS"),
    el("span", {}, swatch("key-bh"), "Capital Buy & Hold"),
  );

  // Vista de tabla: todos los valores accesibles sin pasar el ratón.
  const table = el("details", { class: "data-table" },
    el("summary", { text: "Ver los datos del gráfico en tabla" }),
    el("div", { class: "table-scroll tall" },
      el("table", { class: "factors" },
        el("thead", {}, el("tr", {}, ["Fecha", "Cierre", "Posición", "Capital ARGOS", "Capital B&H"].map((h) => el("th", { text: h })))),
        el("tbody", {}, pts.map((p, i) => el("tr", {},
          el("td", { class: "num", text: p.date }), el("td", { class: "num", text: num2(p.close) }),
          el("td", { text: p.position_qty > 0 ? "comprado" : "liquidez" }),
          el("td", { class: "num", text: money(p.equity) }), el("td", { class: "num", text: money(bh[i].equity) })))))));
  $("bt-chart").replaceChildren(wrap, legend, table);
}
