/* ============================================================
   eBay Auction Dashboard — Frontend Logic
   ============================================================ */

const STRATEGY_LABEL = { GMV: "maximize GMV", traffic: "fast sell", custom: "custom" };
const STRATEGY_COLOR = { GMV: "#378ADD", traffic: "#1D9E75", custom: "#BA7517" };

let allProducts   = [];
let currentFilter = "all";
let distChart     = null;
let strChart      = null;
let miniChart     = null;
let pollTimer     = null;

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  fetchPortfolio();
  fetchProducts();
  fetchFunnel();
  fetchDistChart();
  fetchStrChart();
  pollSimStatus();
});

// ── Utilities ─────────────────────────────────────────────────────────────────
const fmt  = (n, d = 0) => n == null ? "—" : n.toLocaleString("en-US", { maximumFractionDigits: d });
const fmtD = (n, d = 1) => n == null ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtUSD = n => n == null ? "—" : "$" + fmt(n);
const fmtPct = n => n == null ? "—" : (n * 100).toFixed(0) + "%";

function stratBadge(type) {
  const cls   = type === "GMV" ? "strat-gmv" : type === "traffic" ? "strat-fast" : "strat-custom";
  const label = STRATEGY_LABEL[type] || type;
  return `<span class="strat-badge ${cls}">${label}</span>`;
}

// ── Portfolio KPIs ────────────────────────────────────────────────────────────
async function fetchPortfolio() {
  const d = await fetch("/api/portfolio").then(r => r.json());

  const strVal    = d.sim_avg_str != null ? fmtPct(d.sim_avg_str) : "—";
  const dist      = d.strategy_dist || {};
  const simBadge  = document.getElementById("sim-badge");
  if (simBadge) simBadge.textContent = `Monte Carlo n=300`;

  const badge = document.getElementById("products-badge");
  if (badge) badge.textContent = `${d.products} products`;

  document.getElementById("kpi-grid").innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Actual total GMV</div>
      <div class="kpi-value">${fmtUSD(d.actual_gmv)}</div>
      <div class="kpi-sub kpi-up">Real sold prices</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg sell-through rate</div>
      <div class="kpi-value">${strVal}</div>
      <div class="kpi-sub">Baseline: ${fmtPct(d.baseline_str)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Avg bid count / item</div>
      <div class="kpi-value">${fmtD(d.avg_bids)}</div>
      <div class="kpi-sub kpi-up">Total bids per auction</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Strategy mix</div>
      <div class="kpi-value strat-mix">
        <span style="color:#378ADD">GMV ${dist.GMV || 0}</span>
        <span style="color:#1D9E75">Fast ${dist.traffic || 0}</span>
        <span style="color:#BA7517">Custom ${dist.custom || 0}</span>
      </div>
      <div class="kpi-sub">across ${d.products} products</div>
    </div>
  `;
}

// ── Products table ────────────────────────────────────────────────────────────
async function fetchProducts() {
  const d     = await fetch("/api/products").then(r => r.json());
  allProducts = d.products;
  updateTabCounts();
  renderTable();
}

function updateTabCounts() {
  const counts = { all: allProducts.length };
  allProducts.forEach(p => { counts[p.function_type] = (counts[p.function_type] || 0) + 1; });
  const labels = { all: "All", GMV: "GMV", traffic: "Fast sell", custom: "Custom" };
  document.querySelectorAll(".tab-btn").forEach(btn => {
    const type = btn.dataset.type;
    if (type && counts[type] !== undefined) {
      btn.textContent = `${labels[type]} (${counts[type]})`;
    }
  });
}

function filterTable(type, btn) {
  currentFilter = type;
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderTable();
}

function renderTable() {
  const list   = currentFilter === "all" ? allProducts
                 : allProducts.filter(p => p.function_type === currentFilter);
  const tbody  = document.getElementById("rec-tbody");

  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No products in this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(p => {
    const strColor = p.sim_str != null
      ? (p.sim_str >= 0.80 ? "var(--success-text)" : p.sim_str < 0.65 ? "var(--danger)" : "var(--text-primary)")
      : "";

    const recStart = p.rec_start_price != null
      ? `${fmtUSD(p.rec_start_price)} <span class="cell-ratio">(${fmtPct(p.rec_start_price_ratio)})</span>`
      : `<span class="cell-dim">Computing…</span>`;

    const recInterval = p.rec_interval != null
      ? `${fmtUSD(p.rec_interval)}`
      : `<span class="cell-dim">—</span>`;

    const recDuration = p.rec_duration != null
      ? `${p.rec_duration}r`
      : `<span class="cell-dim">—</span>`;

    const simStr = p.sim_str != null
      ? `<span style="color:${strColor};font-weight:600">${fmtPct(p.sim_str)}</span>`
      : `<span class="cell-dim">—</span>`;

    return `
      <tr>
        <td>
          <div class="prod-id">${p.product_id}${p.is_virtual ? `<span class="virtual-pill">virtual</span>` : ""}</div>
          <div class="prod-title" title="${p.short_title}">${p.short_title}</div>
        </td>
        <td class="cell-num">${fmtUSD(p.market_price)}</td>
        <td class="cell-num">
          ${fmtUSD(p.actual_start_price)}
          <span class="cell-ratio">(${fmtPct(p.actual_sp_ratio)})</span>
        </td>
        <td class="cell-num">${recStart}</td>
        <td class="cell-num">${fmtUSD(p.actual_interval)}</td>
        <td class="cell-num">${recInterval}</td>
        <td class="cell-num">${recDuration}</td>
        <td class="cell-num">${simStr}</td>
        <td>${stratBadge(p.function_type)}</td>
      </tr>`;
  }).join("");
}

// ── Funnel ────────────────────────────────────────────────────────────────────
async function fetchFunnel() {
  const d  = await fetch("/api/charts/funnel").then(r => r.json());
  const el = document.getElementById("funnel-section");
  el.innerHTML = d.stages.map((stage, i) => `
    <div class="funnel-row">
      <div class="funnel-label">${stage}</div>
      <div class="funnel-bar-wrap">
        <div class="funnel-bar" style="width:${d.pcts[i]}%;background:${d.colors[i]}">
          ${fmtD(d.values[i])}
        </div>
      </div>
      <div class="funnel-pct">${d.pcts[i]}%</div>
    </div>`).join("");
}

// ── Charts ────────────────────────────────────────────────────────────────────
const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: "#888", font: { size: 10 }, boxWidth: 10, padding: 14 } }
  },
};

async function fetchDistChart() {
  const d   = await fetch("/api/charts/distribution").then(r => r.json());
  const ctx = document.getElementById("distChart");
  const cls = ["#378ADD", "#1D9E75", "#D85A30", "#BA7517"];

  if (distChart) distChart.destroy();
  distChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: d.labels,
      datasets: Object.entries(d.datasets).map(([label, vals], i) => ({
        label,
        data:            vals,
        borderColor:     cls[i],
        backgroundColor: cls[i] + "14",
        fill:            true,
        tension:         0.4,
        pointRadius:     2,
        borderWidth:     2,
      })),
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        x: { ticks: { color: "#888", font: { size: 10 } }, grid: { color: "rgba(0,0,0,0.05)" },
             title: { display: true, text: "Final price / market price", color: "#888", font: { size: 10 } } },
        y: { ticks: { color: "#888", font: { size: 10 } }, grid: { color: "rgba(0,0,0,0.05)" },
             title: { display: true, text: "Simulation count", color: "#888", font: { size: 10 } } },
      },
    },
  });
}

async function fetchStrChart() {
  const d   = await fetch("/api/charts/str").then(r => r.json());
  const ctx = document.getElementById("strChart");
  const barColors = ["#1D9E75","#378ADD","#378ADD","#378ADD","#BA7517","#D85A30","#D85A30"];

  if (strChart) strChart.destroy();
  strChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: d.theoretical.ratios.map(r => `${(r * 100).toFixed(0)}%`),
      datasets: [{
        label: "Sell-through rate",
        data:            d.theoretical.str,
        backgroundColor: barColors,
        borderRadius:    4,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      plugins: { ...CHART_DEFAULTS.plugins, legend: { display: false } },
      scales: {
        x: { ticks: { color: "#888", font: { size: 11 } }, grid: { display: false },
             title: { display: true, text: "Start price / market price", color: "#888", font: { size: 10 } } },
        y: { min: 0, max: 1,
             ticks: { color: "#888", font: { size: 10 }, callback: v => (v * 100).toFixed(0) + "%" },
             grid: { color: "rgba(0,0,0,0.05)" } },
      },
    },
  });
}

// ── Simulation status polling ─────────────────────────────────────────────────
async function pollSimStatus() {
  const s = await fetch("/api/sim/status").then(r => r.json());
  updateSimBadge(s);

  if (s.running) {
    if (!pollTimer) {
      pollTimer = setInterval(async () => {
        const status = await fetch("/api/sim/status").then(r => r.json());
        updateSimBadge(status);
        if (status.done || status.error) {
          clearInterval(pollTimer); pollTimer = null;
          // Reload data with recommendations
          fetchPortfolio();
          fetchProducts();
        }
      }, 2000);
    }
  }
}

function updateSimBadge(s) {
  const badge = document.getElementById("computing-badge");
  const bar   = document.getElementById("progress-bar");

  if (!badge) return;

  if (s.running) {
    badge.style.display = "";
    badge.textContent   = `Computing… ${s.progress}/${s.total}`;
    if (bar && s.total > 0) {
      bar.style.width = `${(s.progress / s.total * 100).toFixed(1)}%`;
      bar.parentElement.style.display = "";
    }
  } else {
    badge.style.display = "none";
    if (bar) bar.parentElement.style.display = "none";
  }
}

// ── Refresh simulation ────────────────────────────────────────────────────────
async function refreshSimulation() {
  const ok = confirm("This will re-run all Monte Carlo simulations (takes ~1–3 min). Continue?");
  if (!ok) return;
  await fetch("/api/refresh", { method: "POST" });
  allProducts = allProducts.map(p => {
    const copy = { ...p };
    delete copy.rec_start_price; delete copy.rec_interval; delete copy.rec_duration;
    delete copy.sim_str; delete copy.sim_p50; delete copy.avg_bids_sim;
    return copy;
  });
  renderTable();
  pollSimStatus();
}

// ── New product simulator ─────────────────────────────────────────────────────
async function runSimulator() {
  const price   = parseFloat(document.getElementById("sim-price").value);
  const type    = document.getElementById("sim-type").value;
  const viewers = parseInt(document.getElementById("sim-viewers").value) || 80;

  if (!price || price <= 0) { alert("Enter a valid market price."); return; }

  const btn = document.getElementById("run-btn");
  btn.disabled   = true;
  btn.textContent = "Running…";

  const resultArea = document.getElementById("sim-result");
  resultArea.innerHTML = `<div class="sim-result-placeholder">Simulating ${price >= 1000 ? "high-value" : price >= 100 ? "mid-range" : "low-value"} product…</div>`;

  try {
    const r = await fetch("/api/sim/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ market_price: price, function_type: type, viewers }),
    }).then(res => res.json());

    renderSimResult(r);
  } catch (e) {
    resultArea.innerHTML = `<div class="sim-result-placeholder" style="color:var(--danger)">Error: ${e.message}</div>`;
  } finally {
    btn.disabled    = false;
    btn.textContent = "Run Simulation";
  }
}

function renderSimResult(r) {
  const area    = document.getElementById("sim-result");
  const type    = r.function_type || "GMV";
  const tColor  = type === "GMV" ? "var(--info-text)"    : type === "traffic" ? "var(--success-text)" : "var(--warning-text)";
  const tBg     = type === "GMV" ? "var(--info-bg)"      : type === "traffic" ? "var(--success-bg)"   : "var(--warning-bg)";
  const strPct  = r.sell_through_rate != null ? fmtPct(r.sell_through_rate) : "—";
  const strStyle = r.sell_through_rate >= 0.80 ? "color:var(--success-text)" :
                   r.sell_through_rate  < 0.65 ? "color:var(--danger)" : "";

  const params = [
    ["Rec. Start Price", `${fmtUSD(r.rec_start_price)} <small style="color:var(--text-tertiary)">(${fmtPct(r.rec_start_price_ratio)})</small>`],
    ["Rec. Interval",    fmtUSD(r.rec_price_interval)],
    ["Rec. Duration",    `${r.rec_duration} rounds`],
    ["p50 Final Price",  fmtUSD(r.price_p50)],
    ["Sim. Sell-Through",`<span style="${strStyle};font-weight:600">${strPct}</span>`],
    ["Avg Bids",         fmtD(r.avg_bids)],
  ];

  area.innerHTML = `
    <div class="sim-result-header">
      <span class="sim-result-title">Simulation Result</span>
      <span class="strat-badge" style="background:${tBg};color:${tColor}">${STRATEGY_LABEL[type] || type}</span>
    </div>
    <div class="param-grid">
      ${params.map(([k, v]) => `
        <div class="param-row">
          <span class="param-key">${k}</span>
          <span class="param-val">${v}</span>
        </div>`).join("")}
    </div>
    ${r.dist_data ? `<div class="mini-chart-wrap"><canvas id="miniChart"></canvas></div>` : ""}
  `;

  if (r.dist_data) {
    setTimeout(() => {
      const ctx = document.getElementById("miniChart");
      if (!ctx) return;
      if (miniChart) miniChart.destroy();
      const cls = ["#378ADD", "#1D9E75", "#D85A30", "#BA7517"];
      miniChart = new Chart(ctx, {
        type: "line",
        data: {
          labels: r.dist_labels,
          datasets: Object.entries(r.dist_data).map(([label, vals], i) => ({
            label,
            data:            vals,
            borderColor:     cls[i],
            backgroundColor: cls[i] + "14",
            fill:            true,
            tension:         0.4,
            pointRadius:     0,
            borderWidth:     1.5,
          })),
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: "#888", font: { size: 9 }, boxWidth: 8, padding: 10 } } },
          scales: {
            x: { ticks: { color: "#888", font: { size: 9 } }, grid: { display: false } },
            y: { ticks: { color: "#888", font: { size: 9 } }, grid: { color: "rgba(0,0,0,0.05)" } },
          },
        },
      });
    }, 30);
  }
}
