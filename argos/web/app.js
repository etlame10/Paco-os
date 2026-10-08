// ARGOS — interfaz web. Solo lee de la API local (/api/...). No contiene
// claves ni credenciales: todo el acceso a datos ocurre en el servidor.
"use strict";

const $ = (id) => document.getElementById(id);

// Crea elementos de forma segura: el texto siempre va por textContent.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const nf = (d) => new Intl.NumberFormat("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });

function fmtValue(value, unit) {
  if (value === null || value === undefined) return "n/d";
  if (typeof value !== "number") return String(value);
  if (unit === "%") return `${nf(2).format(value * 100)} %`;
  if (unit === "x") return `${nf(2).format(value)}×`;
  if (Number.isInteger(value) || Math.abs(value) >= 10000) return nf(0).format(value);
  return nf(2).format(value);
}

const layerBadge = (layer) => {
  const names = { dato: "Dato", indicador: "Indicador", interpretacion: "Interpretación", conclusion: "Conclusión" };
  return el("span", { class: `layer layer-${layer}`, text: names[layer] || layer });
};
const stanceChip = (stance) => el("span", { class: `stance stance-${stance}`, text: stance });

// ------------------------------------------------------------------ inicio

async function loadProviders() {
  try {
    const res = await fetch("/api/providers");
    const { providers } = await res.json();
    const chips = $("ticker-chips");
    chips.replaceChildren();
    let realCount = 0;
    for (const p of providers) {
      for (const t of p.tickers || []) {
        if (!p.is_simulated) realCount++;
        const chip = el("button", { type: "button", class: `chip${p.is_simulated ? " chip-demo" : ""}`, text: t });
        chip.addEventListener("click", () => { $("ticker-input").value = t; analyze(t); });
        chips.append(chip);
      }
    }
    $("data-hint").textContent = realCount
      ? `Hay ${realCount} activo(s) con datos reales importados (CSV) y tickers de demostración.`
      : "Todavía no hay ninguna fuente de datos reales conectada: solo están disponibles los tickers de demostración (datos simulados de empresas ficticias).";
  } catch {
    $("data-hint").textContent = "No se pudo contactar con el servidor de ARGOS.";
  }
}

async function loadHealth() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("pill-trading").textContent = h.live_trading_enabled ? "Operativa real: ACTIVADA" : "Operativa real: DESACTIVADA";
  } catch { /* la cabecera conserva el valor seguro por defecto */ }
}

// ---------------------------------------------------------------- análisis

async function analyze(raw) {
  const ticker = (raw || "").trim().toUpperCase();
  if (!ticker) return;
  const btn = $("analyze-btn");
  btn.disabled = true;
  btn.textContent = "Analizando…";
  $("error-box").hidden = true;
  try {
    const res = await fetch(`/api/analyze/${encodeURIComponent(ticker)}`);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || `Error ${res.status}`);
    render(body);
  } catch (err) {
    $("results").hidden = true;
    $("demo-banner").hidden = true;
    $("error-box").textContent = err.message;
    $("error-box").hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Analizar";
  }
}

function render(r) {
  const simulated = r.provenance.is_simulated;
  $("demo-banner").hidden = !simulated;
  if (simulated) $("demo-banner-text").textContent = r.provenance.warning;

  // Etiqueta "DEMO" en cada panel cuando los datos son simulados.
  document.querySelectorAll(".panel > header").forEach((h) => {
    h.querySelector(".demo-tag")?.remove();
    if (simulated) h.append(el("span", { class: "demo-tag", text: "DATOS DEMO" }));
  });

  renderAsset(r);
  renderChart(r.chart);
  renderIndicators(r.indicators);
  renderAnalysis(r);
  renderRisk(r.risk);
  renderConclusion(r.conclusion);
  renderExplanation(r.explanation);
  $("results").hidden = false;
}

function renderAsset(r) {
  const p = r.provenance;
  const rows = r.data.map((d) => el("tr", {}, el("td", { text: d.label }), el("td", { text: fmtValue(d.value, d.unit) })));
  $("asset-body").replaceChildren(
    el("p", { class: "asset-name", text: r.asset.name }),
    el("p", { class: "asset-meta", text: [r.asset.ticker, r.asset.asset_type, r.asset.exchange, r.asset.currency].filter(Boolean).join(" · ") }),
    el("table", { class: "kv" }, el("tbody", {}, rows)),
    el("div", { class: `provenance${p.is_simulated ? " simulated" : ""}` },
      el("b", { text: "Fuente: " }), `${p.source_description} (proveedor «${p.provider}»). `,
      p.is_simulated ? "SIMULADO. " : "",
      p.warning || ""),
  );
}

function renderChart(c) {
  const W = 720, H = 240, pad = 8;
  const all = [...c.close, ...c.sma50, ...c.sma200].filter((v) => v !== null);
  const min = Math.min(...all), max = Math.max(...all);
  const x = (i) => pad + (i / Math.max(1, c.close.length - 1)) * (W - 2 * pad);
  const y = (v) => H - pad - ((v - min) / (max - min || 1)) * (H - 2 * pad);
  const path = (series) => {
    let d = "", pen = false;
    series.forEach((v, i) => {
      if (v === null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "chart");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Gráfico de precio de cierre con medias móviles de 50 y 200 sesiones");
  for (const [series, color, width] of [[c.sma200, "#b18cff", 1.5], [c.sma50, "#ffb547", 1.5], [c.close, "#7cf2d4", 2]]) {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", path(series));
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", color);
    p.setAttribute("stroke-width", width);
    svg.append(p);
  }
  const swatch = (color) => { const i = el("i"); i.style.background = color; return i; };
  const legend = el("div", { class: "chart-legend" },
    el("span", {}, swatch("#7cf2d4"), "Cierre (dato)"),
    el("span", {}, swatch("#ffb547"), "SMA 50 (indicador)"),
    el("span", {}, swatch("#b18cff"), "SMA 200 (indicador)"),
    el("span", { text: `${c.dates[0]} → ${c.dates[c.dates.length - 1]} · mín ${fmtValue(min)} · máx ${fmtValue(max)}` }),
  );
  $("chart-body").replaceChildren(svg, legend);
}

function renderIndicators(list) {
  const rows = list.map((i) =>
    el("tr", {},
      el("td", {}, i.name, el("span", { class: "method", text: i.method })),
      el("td", { text: fmtValue(i.value, i.unit) })));
  $("indicators-body").replaceChildren(el("table", { class: "kv" }, el("tbody", {}, rows)));
}

function interpretationCard(i, lookup) {
  const evidence = i.evidence.map((id) => {
    const item = lookup[id];
    return item ? `${item.name || item.label} = ${fmtValue(item.value, item.unit)}` : id;
  }).join(" · ");
  return el("details", { class: "interp" },
    el("summary", {}, stanceChip(i.stance), el("span", {}, el("span", { class: "interp-area", text: i.area }), el("br"), i.statement)),
    el("p", { class: "interp-detail" }, el("b", { text: "Regla: " }), i.rule),
    el("p", { class: "interp-detail" }, el("b", { text: "Basado en: " }), evidence),
    i.caveat ? el("p", { class: "interp-detail" }, el("b", { text: "Limitación: " }), i.caveat) : null,
  );
}

let lookup = {};
function renderAnalysis(r) {
  lookup = {};
  for (const d of r.data) lookup[d.id] = d;
  for (const i of r.indicators) lookup[i.id] = i;
  for (const m of r.risk.metrics) lookup[m.id] = m;
  $("analysis-body").replaceChildren(
    el("h3", { text: "Técnico" }),
    ...r.interpretations.map((i) => interpretationCard(i, lookup)),
    el("h3", { text: "Fundamental" }),
    el("p", { class: "status-note", text: r.fundamental.note }),
    el("h3", { text: "Noticias y contexto" }),
    el("p", { class: "status-note", text: r.news.note }),
  );
}

function renderRisk(risk) {
  $("risk-body").replaceChildren(
    el("p", { class: "risk-level", text: `Riesgo ${risk.level}` }),
    el("table", { class: "kv" }, el("tbody", {}, risk.metrics.map((m) =>
      el("tr", {}, el("td", {}, m.name, el("span", { class: "method", text: m.method })), el("td", { text: fmtValue(m.value, m.unit) }))))),
    el("h3", { text: "Interpretación" }),
    ...risk.interpretations.map((i) => interpretationCard(i, lookup)),
    el("h3", { text: "Escenarios estadísticos (no son predicciones)" }),
    ...risk.scenarios.map((s) => el("div", { class: "scenario" }, el("b", { text: `${s.name}: ` }), s.description, el("small", { text: s.basis }))),
  );
}

function renderConclusion(c) {
  const pos = ((c.score + 1) / 2) * 100;
  const marker = el("span", { class: "marker" });
  marker.style.left = `${pos}%`;
  const factorRows = c.factors.map((f) =>
    el("tr", {},
      el("td", { text: f.area }),
      el("td", { text: f.statement }),
      el("td", {}, stanceChip(f.stance)),
      el("td", { class: "num", text: f.weight }),
      el("td", { class: "num", text: (f.contribution > 0 ? "+" : "") + f.contribution })));
  $("conclusion-body").replaceChildren(
    el("p", { class: "conclusion-label", text: c.label }),
    el("p", { class: "conclusion-summary", text: c.summary }),
    el("div", { class: "scorebar", title: `Puntuación ${c.score}` }, marker),
    el("div", { class: "scorebar-scale" }, el("span", { text: "−1 bajista" }), el("span", { text: `puntuación ${nf(2).format(c.score)}` }), el("span", { text: "+1 alcista" })),
    el("h3", { text: "De dónde sale (factores)" }),
    el("table", { class: "factors" },
      el("thead", {}, el("tr", {}, ["Área", "Interpretación", "Sesgo", "Peso", "Aporta"].map((h) => el("th", { text: h })))),
      el("tbody", {}, factorRows)),
    el("p", { class: "interp-detail" }, el("b", { text: "Método: " }), c.score_method),
    el("p", { class: "interp-detail" }, el("b", { text: "Coherencia: " }), c.agreement_note),
    el("div", { class: "disclaimer-box", text: c.disclaimer }),
  );
}

function renderExplanation(e) {
  $("explanation-body").replaceChildren(
    ...e.sections.map((s) => el("div", { class: "explain-section" }, el("h3", { text: s.title }), el("p", { text: s.text }))),
    el("p", { class: "interp-detail" }, el("b", { text: "Generado por: " }), `${e.generator}. ${e.method_note}`),
  );
}

$("search-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  analyze($("ticker-input").value);
});

loadHealth();
loadProviders();
