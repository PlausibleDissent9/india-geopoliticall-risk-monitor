/* IGRM frontend. Reads only what the pipeline writes into docs/data/. */

const COLORS = {
  composite: "#12233D",
  pakistan_west: "#A2361F",
  china_east: "#B07C1F",
  gulf_energy: "#1E6E67",
  us_trade: "#4A5D8A",
  shipping: "#7A6A54",
};

const state = { history: null, range: 365, on: { composite: true } };
let chart = null;

function stateColor(score) {
  if (score >= 70) return getCSS("--severe");
  if (score >= 45) return getCSS("--elevated");
  return getCSS("--calm");
}
function getCSS(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
function fmtDelta(d) {
  const cls = d > 0.05 ? "up" : d < -0.05 ? "down" : "flat";
  const arrow = d > 0.05 ? "\u25B2" : d < -0.05 ? "\u25BC" : "\u2013";
  return `<span class="${cls}">${arrow} ${d >= 0 ? "+" : ""}${d.toFixed(1)}</span>`;
}

async function loadJSON(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function renderLatest(latest) {
  const score = latest.composite.score;
  document.documentElement.style.setProperty("--state", stateColor(score));
  document.getElementById("latest-date").textContent = latest.date;
  document.getElementById("composite-score").textContent = score.toFixed(1);
  document.getElementById("composite-delta").innerHTML =
    `${fmtDelta(latest.composite.delta_1d)} <span class="flat">vs yesterday</span>`;
  document.getElementById("band-tick").style.left =
    `${Math.max(0, Math.min(100, score))}%`;

  const wrap = document.getElementById("components");
  wrap.innerHTML = "";
  for (const [key, c] of Object.entries(latest.components)) {
    const row = document.createElement("div");
    row.className = "component-row";
    row.innerHTML =
      `<span class="component-name">${c.label}</span>` +
      `<span class="component-score">${c.score.toFixed(1)}</span>` +
      `<span class="component-delta">${fmtDelta(c.delta_1d)}</span>`;
    wrap.appendChild(row);
  }
}

function sliceRange(arr, n) {
  return n === "all" ? arr : arr.slice(-n);
}

function renderChart() {
  const h = state.history;
  if (!h) return;
  const labels = sliceRange(h.dates, state.range);
  const datasets = [];
  const addSeries = (key, data, label) => {
    if (!state.on[key]) return;
    datasets.push({
      label,
      data: sliceRange(data, state.range),
      borderColor: COLORS[key] || "#888",
      borderWidth: key === "composite" ? 2.2 : 1.2,
      pointRadius: 0,
      tension: 0.2,
    });
  };
  addSeries("composite", h.composite, "Composite");
  for (const [key, data] of Object.entries(h.components)) {
    addSeries(key, data, (h.labels && h.labels[key]) || key);
  }
  const ctx = document.getElementById("history-chart");
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      animation: false,
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, grid: { color: "#EAE8E0" } },
        x: { ticks: { maxTicksLimit: 8 }, grid: { display: false } },
      },
    },
  });
}

function buildToggles(h) {
  const wrap = document.getElementById("series-toggles");
  const keys = ["composite", ...Object.keys(h.components)];
  for (const key of keys) {
    state.on[key] = key === "composite";
    const b = document.createElement("button");
    b.className = "toggle" + (state.on[key] ? " is-on" : "");
    b.textContent = key === "composite" ? "Composite"
      : (h.labels && h.labels[key]) || key;
    b.addEventListener("click", () => {
      state.on[key] = !state.on[key];
      b.classList.toggle("is-on", state.on[key]);
      renderChart();
    });
    wrap.appendChild(b);
  }
}

function bindRanges() {
  document.querySelectorAll(".range-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelectorAll(".range-btn").forEach((x) =>
        x.classList.remove("is-active"));
      b.classList.add("is-active");
      const r = b.dataset.range;
      state.range = r === "all" ? "all" : parseInt(r, 10);
      renderChart();
    });
  });
}

/* Minimal markdown for the weekly note (headings, bold, lists, paras). */
function miniMarkdown(md) {
  const esc = md.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const body = esc.replace(/^---[\s\S]*?---\s*/, ""); // strip front matter
  return body
    .split(/\n{2,}/)
    .map((block) => {
      const b = block.trim();
      if (!b) return "";
      if (b.startsWith("## ")) return `<h3>${b.slice(3)}</h3>`;
      if (b.split("\n").every((l) => l.trim().startsWith("- "))) {
        const items = b.split("\n")
          .map((l) => `<li>${l.trim().slice(2)}</li>`).join("");
        return `<ul>${items}</ul>`;
      }
      return `<p>${b.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>")}</p>`;
    })
    .join("");
}

function renderEpisodes(episodes) {
  const tbody = document.querySelector("#episodes-table tbody");
  if (!episodes || !episodes.length) return;
  tbody.innerHTML = "";
  for (const e of episodes.slice(0, 40)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.start}</td><td>${e.end}</td>` +
      `<td>${e.channel}</td><td>${Number(e.peak).toFixed(1)}</td>` +
      `<td>${e.days}</td>`;
    tbody.appendChild(tr);
  }
}

async function init() {
  bindRanges();
  try {
    const latest = await loadJSON("data/latest.json");
    renderLatest(latest);
  } catch (e) { console.warn("latest.json not available yet", e); }
  try {
    state.history = await loadJSON("data/history.json");
    buildToggles(state.history);
    renderChart();
  } catch (e) { console.warn("history.json not available yet", e); }
  try {
    const note = await loadJSON("data/note_latest.json");
    if (note.markdown) {
      document.getElementById("weekly-note").innerHTML =
        miniMarkdown(note.markdown);
    }
  } catch (e) { /* no note yet */ }
  try {
    const eps = await loadJSON("data/episodes.json");
    renderEpisodes(eps);
  } catch (e) { /* no episodes yet */ }
}

init();
