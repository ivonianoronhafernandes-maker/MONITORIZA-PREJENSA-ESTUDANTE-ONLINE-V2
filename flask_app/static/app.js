const $ = (s, r = document) => r.querySelector(s);
const fmt = n => Number(n).toLocaleString("en-US").replace(/,/g, ".");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const COL = { prezente: "#1d6bf3", atrazadu: "#f59e0b", falta: "#ef4444", lisensa: "#8b5cf6", saisedu: "#14b8a6" };
const ICON = { Prezente: "✔", Atrazadu: "◷", Falta: "✖", Lisensa: "✉", "Sai Sedu": "⇦" };
const debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

function pill(s) { return `<span class="pill ${s.replace(" ", "")}">${ICON[s] || ""} ${esc(s)}</span>`; }

function lineChart(el, d) {
  const W = 760, H = 300, L = 46, R = 16, T = 18, B = 34, n = d.label.length, iw = W - L - R, ih = H - T - B;
  const mx = Math.max(...d.prezente, ...d.atrazadu, ...d.falta) <= 40 ? 40 : 100, ticks = mx === 40 ? [0, 10, 20, 30, 40] : [0, 20, 40, 60, 80, 100];
  const x = i => L + (n === 1 ? iw / 2 : (iw * i) / (n - 1)), y = v => T + ih - (ih * v) / mx;
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  ticks.forEach(v => s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="#e6edf8"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" font-size="12" fill="#334155">${v}%</text>`);
  d.label.forEach((l, i) => s += `<text x="${x(i)}" y="${H - 10}" text-anchor="middle" font-size="12" fill="#334155">${esc(l)}</text>`);
  [["falta", d.falta], ["atrazadu", d.atrazadu], ["prezente", d.prezente]].forEach(([k, arr]) => {
    const p = arr.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    s += `<polygon points="${x(0)},${y(0)} ${p} ${x(n - 1)},${y(0)}" fill="${COL[k]}" opacity=".08"/><polyline points="${p}" fill="none" stroke="${COL[k]}" stroke-width="2.5"/>`;
    arr.forEach((v, i) => s += `<circle cx="${x(i)}" cy="${y(v)}" r="4.5" fill="${COL[k]}" stroke="#fff" stroke-width="1.5"><title>${d.label[i]}: ${v}%</title></circle>`);
  });
  el.innerHTML = s + "</svg>";
}

function donut(el, list, t) {
  const R = 78, C = 2 * Math.PI * R; let off = 0, s = `<svg viewBox="0 0 200 200"><g transform="rotate(-90 100 100)">`;
  list.forEach(([k, v]) => { const len = (C * v) / 100; s += `<circle cx="100" cy="100" r="${R}" fill="none" stroke="${COL[k]}" stroke-width="30" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}"/>`; off += len; });
  el.innerHTML = s + `</g><text x="100" y="104" text-anchor="middle" font-size="34" font-weight="800" fill="#0f2a5c">${t.p_Prezente}%</text><text x="100" y="128" text-anchor="middle" font-size="15" fill="#0f2a5c">Prezente</text></svg>`;
}

function renderDash(d) {
  const t = d.totals;
  lineChart($("#lineChart"), d.series);
  const rows = [["prezente", "Prezente"], ["atrazadu", "Atrazadu"], ["falta", "Falta"], ["lisensa", "Lisensa"], ["saisedu", "Sai Sedu"]];
  donut($("#donut"), rows.map(([k, n]) => [k, t["p_" + n]]), t);
  $("#dlist").innerHTML = rows.map(([k, n]) => `<li><i style="background:${COL[k]}"></i><b>${n}</b><span>${fmt(t[n])} (${t["p_" + n]}%)</span></li>`).join("");
  $("#ins").innerHTML = d.insights.map((r, i) => {
    const c = ["#1d6bf3", "#f59e0b", "#ef4444"][i], ic = ["▮▮", "◷", "✖"][i];
    return `<li><span class="ico" style="background:${c}">${ic}</span><span class="t">${esc(r.label)}</span><b>${r.valor.toFixed(1)}%</b><em class="${r.bom ? "up" : "dn"}">${r.delta >= 0 ? "↑ +" : "↓ "}${r.delta.toFixed(1)}%</em></li>`;
  }).join("");
}

function table(cfg) {
  const st = { page: 1, estatutu: "", q: "" }, tb = $("#tbl tbody");
  async function load() {
    const p = new URLSearchParams({ page: st.page, size: cfg.size, ...cfg.params(st) });
    const d = await (await fetch(cfg.url + "?" + p)).json();
    tb.innerHTML = d.rows.length ? d.rows.map(cfg.row).join("") : `<tr><td colspan="12" class="muted" style="text-align:center;padding:24px">Dadus la hetan.</td></tr>`;
    const a = (d.page - 1) * cfg.size + 1, b = Math.min(d.page * cfg.size, d.total);
    $("#info").textContent = d.total ? `Hatudu ${fmt(a)}–${fmt(b)} husi ${fmt(d.total)}` : "";
    const pg = $("#pager");
    pg.innerHTML = `<button ${d.page <= 1 ? "disabled" : ""} data-g="${d.page - 1}">‹ Antes</button><span style="padding:6px 8px">${fmt(d.page)} / ${fmt(d.pages)}</span><button ${d.page >= d.pages ? "disabled" : ""} data-g="${d.page + 1}">Tuir ›</button>`;
    pg.querySelectorAll("button").forEach(x => x.onclick = () => { st.page = +x.dataset.g; load(); });
    if ($("#exp") && cfg.exp) $("#exp").href = cfg.exp + "?" + new URLSearchParams(cfg.params(st));
  }
  const reset = () => { st.page = 1; load(); };
  $("#q").addEventListener("input", debounce(e => { st.q = e.target.value; reset(); }));
  document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => { document.querySelectorAll("#tabs button").forEach(x => x.classList.remove("on")); b.classList.add("on"); st.estatutu = b.dataset.s; reset(); });
  (cfg.filters || []).forEach(id => $("#" + id).addEventListener("change", reset));
  load();
}

function initDashboard() {
  if (!window.DASH) return;
  renderDash(DASH);
  document.querySelectorAll("#seg button").forEach(b => b.onclick = async () => {
    document.querySelectorAll("#seg button").forEach(x => x.classList.remove("on")); b.classList.add("on");
    renderDash(await (await fetch("/api/dashboard?periodu=" + b.dataset.p)).json());
  });
  table({ url: "/api/prezensa", size: 5, params: s => ({ estatutu: s.estatutu, q: s.q }),
    row: r => `<tr><td>${r.no}</td><td>${esc(r.naran)}</td><td>${esc(r.nim)}</td><td>${esc(r.klase)}</td><td>${r.data}</td><td>${r.oras}</td><td>${pill(r.estatutu)}</td></tr>` });
}

function initPrezensa() {
  const v = id => $("#" + id).value;
  table({ url: "/api/prezensa", size: 15, exp: "/export/prezensa.csv", filters: ["f-disiplina", "f-klase", "f-dari", "f-too"],
    params: s => ({ estatutu: s.estatutu, q: s.q, disiplina: v("f-disiplina"), klase: v("f-klase"), dari: v("f-dari"), too: v("f-too") }),
    row: r => `<tr><td>${r.no}</td><td>${esc(r.naran)}</td><td>${esc(r.nim)}</td><td>${esc(r.klase)}</td><td>${esc(r.disiplina)}</td><td>${r.data}</td><td>${r.oras}</td><td>${pill(r.estatutu)}</td></tr>` });
}

function initEstudante() {
  let n = 0;
  table({ url: "/api/estudante", size: 12, exp: "/export/estudante.csv", filters: ["f-klase"], params: s => ({ q: s.q, klase: $("#f-klase").value }),
    row: r => { n++; return `<tr><td>${n}</td><td>${esc(r.naran)}</td><td>${esc(r.id)}</td><td>${esc(r.klase)}</td><td>${r.data_moris}</td><td>${fmt(r.total)}</td><td>${fmt(r.prezente)}</td><td>${fmt(r.atrazadu)}</td><td>${fmt(r.falta)}</td><td><b>${r.pct}%</b></td></tr>`; } });
  // nomor urut tuir pájina
  const tb = $("#tbl tbody"); new MutationObserver(() => { n = 0; }).observe(tb, { childList: true });
}

function stacked(el, arr) {
  el.className = "bars";
  el.innerHTML = arr.map(r => `<div class="hbar"><span>${esc(r.label)}</span><div class="tr"><i style="width:${r.prezente}%;background:${COL.prezente}"></i><i style="width:${r.atrazadu}%;background:${COL.atrazadu}"></i><i style="width:${r.falta}%;background:${COL.falta}"></i></div><b>${r.prezente}%</b></div>`).join("");
}
function single(el, arr, color, suffix) {
  const max = Math.max(...arr.map(r => r.valor), 1);
  el.innerHTML = arr.map(r => `<div class="hbar"><span>${esc(r.label)}</span><div class="tr"><i style="width:${(r.valor / max) * 100}%;background:${color}"></i></div><b>${r.valor}${suffix}</b></div>`).join("");
}
function initAnalytics() {
  stacked($("#c-dis"), AN.disiplina); stacked($("#c-kla"), AN.klase);
  single($("#c-nota"), AN.nota, "#1d6bf3", ""); single($("#c-tar"), AN.tarefa, "#16a34a", "%");
}
