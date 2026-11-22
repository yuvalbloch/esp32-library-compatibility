"use strict";
// The page markup, built here so the same file serves this repository's page and the page on yuvalbloch.com.
function renderShell() {
  const root = document.getElementById("app");
  const back = CFG.back ? `<div class="backbar"><div class="wrap">${CFG.back.map(([href, label]) => `<a href="${href}">${label}</a>`).join("<span>·</span>")}</div></div>` : "";
  root.innerHTML = back + `<header class="top">
  <div class="wrap">
    <h1>ESP32 Library Compatibility</h1>
    <p class="lede">Which Arduino libraries still compile on <b>Arduino-ESP32 core <span class="target">4.0</span></b>, and which versions to pin.
      Every cell comes from a real compile log — click it to see the log.
      <span class="made">A side project, built with AI as an experiment. <a href="#about" data-goto="made">How this was made</a></span></p>
    <div id="stats" class="stats"></div>
    <nav class="tabs" role="tablist">
      <button data-tab="table" class="active">Table</button>
      <button data-tab="regressions">Broken on <span class="target">4.0</span></button>
      <button data-tab="errors">Error groups</button>
      <button data-tab="pin">Pin tool</button>
      <button data-tab="about">How we test</button>
    </nav>
  </div>
</header>

<main class="wrap">
  <section id="tab-table" class="tab active">
    <div id="news" class="news" hidden></div>
    <div class="controls">
      <input id="q" type="search" placeholder="Search libraries…" aria-label="Search libraries">
      <select id="cat" aria-label="Category"><option value="">All categories</option></select>
      <select id="chipf" aria-label="Chip"><option value="">All chips</option></select>
      <label><input type="checkbox" id="onlyreg"> Only broken on <span class="target">4.0</span></label>
      <label><input type="checkbox" id="allver"> All tested versions</label>
    </div>
    <div class="legend" id="legend"></div>
    <div class="tablewrap"><table id="grid"></table></div>
  </section>

  <section id="tab-regressions" class="tab">
    <p class="note">A library is listed here when its example compiled on core <span class="baseline"></span> and
      fails on core <span class="target"></span> for the same chip and the same library version.</p>
    <div id="reglist"></div>
  </section>

  <section id="tab-errors" class="tab">
    <p class="note">Failures on core <span class="target"></span>, grouped by the first compiler error.
      The group label is an explanation to help readers; the ❌ itself always comes from the compile log.</p>
    <div id="errgroups"></div>
  </section>

  <section id="tab-pin" class="tab">
    <p class="note">Pick your chip, your core and your libraries. The tool picks, for each library, the newest
      version that compiled in our tests, and gives you a lockfile you can paste into your project.</p>
    <div class="pin">
      <div class="pin-in">
        <label>Chip <select id="pchip"></select></label>
        <label>Core <select id="pcore"></select></label>
        <input id="pq" type="search" placeholder="Filter libraries…" aria-label="Filter libraries">
        <div id="plibs" class="plibs"></div>
      </div>
      <div class="pin-out" id="pout"><p class="muted">Select one or more libraries.</p></div>
    </div>
  </section>

  <section id="tab-about" class="tab prose">
    <h2>How we test</h2>
    <p>For each library we take the newest release and up to three previous releases, pick one or two of the
      library's own example sketches, and compile them with <code>arduino-cli</code> against Arduino-ESP32 cores
      <span id="corelist"></span> for the ESP32, ESP32-S3 and ESP32-C3 chips. Each core version is installed in its
      own sealed environment, and each compile is given exactly the library versions listed in its log.</p>
    <p><b>This is a build test, not a hardware test.</b> ✅ means the example compiled and linked. It does not prove
      the library behaves correctly at runtime. ❌ is a strong signal: the code cannot be built with that setup.</p>
    <h3>What the symbols mean</h3>
    <div id="legend2" class="legend"></div>
    <h3>Rules we follow</h3>
    <ul>
      <li>Every status comes from a real compile log. Nobody (human or AI) sets a ✅ or ❌ by hand.</li>
      <li>Compile logs are never edited. A library fix shows up as a new library version with its own row.</li>
      <li>The table updates itself every night: new library releases are compiled as soon as they appear in the
        Arduino Library Manager, and when Espressif releases a new core version it replaces the older release of
        the same line and every library is compiled against it.</li>
      <li>If an example needs a library its own library does not declare (for example a display driver needing a graphics library), we add the library that provides the missing header and record it in the log.</li>
      <li>If a sketch is too big for the default flash layout, we also try the <code>huge_app</code> partition scheme and show the result with ⚙.</li>
      <li>Compiler warnings use the Arduino IDE default (warnings off).</li>
    </ul>
    <h3>Which libraries</h3>
    <p>The most popular ESP32-compatible libraries from the Arduino Library Manager, ranked by popularity and by
      how likely the new core was to break them. Libraries marked <span class="tag">Espressif CI</span> are also
      checked by Espressif's own test, which compiles about ten external libraries; we include them so you can
      compare.</p>
    <h3 id="made">How this was made</h3>
    <p>This is a side project by Yuval Bloch, built as an experiment in AI-driven development: an AI (Claude) planned
      and wrote all the code, and I reviewed and approved each step. I am not an embedded developer. That is why the
      project has one rule it never bends: no human or AI decides a result. Every ✅ and ❌ comes from a real
      <code>arduino-cli</code> compile, and every cell links to its full log and the exact command, so you can
      reproduce it. The code and the data are on
      <a href="https://github.com/yuvalbloch/esp32-library-compatibility">GitHub</a>. If something looks wrong, please
      <a href="https://github.com/yuvalbloch/esp32-library-compatibility/issues/new?template=wrong-result.yml">open a
      “Wrong result” issue</a>.</p>
    <p class="muted" id="gen"></p>
  </section>
</main>

<div id="modal" class="modal" hidden>
  <div class="modal-box" role="dialog" aria-modal="true">
    <button class="close" aria-label="Close">×</button>
    <div id="modal-body"></div>
  </div>
</div>`;
}

// ESP32 Library Compatibility — static front end. Reads data/results.json (exported from the farm's results.db).
// Statuses are displayed exactly as stored; this file only aggregates them for display.

let D, LIBS, ROWS, CELL = new Map();
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const CHIP_NAME = { esp32: "ESP32", esp32s3: "S3", esp32c3: "C3", esp32s2: "S2", esp32c6: "C6", esp32h2: "H2", esp32p4: "P4", esp32c5: "C5" };
const SYM = {
  pass: ["✓", "pass", "Compiles"],
  pass_cfg: ["✓⚙", "pass", "Compiles with non-default board settings (see details)"],
  partial: ["◐", "partial", "Some examples compile, some fail"],
  fail: ["✗", "fail", "Fails to compile"],
  dep_fail: ["dep", "dep_fail", "A library it depends on fails to compile"],
  "n/a": ["—", "na", "Chip lacks a feature the library needs"],
  config: ["⚙", "config", "Needs board settings or a specific board"],
  infra_error: ["?", "infra", "Our farm had a problem; will be retried"],
  none: ["·", "none", "Not tested yet"],
};
const OK = s => s === "pass" || s === "pass_cfg";
const BAD = s => s === "fail" || s === "dep_fail";

// Where data and logs live. The page on yuvalbloch.com sets window.ESP32_COMPAT = {base: "https://…/"};
// the copy in this repository uses relative paths.
const CFG = window.ESP32_COMPAT || {};
const BASE = CFG.base || "";
renderShell();
fetch(BASE + "data/results.json").then(r => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(init).catch(e => {
  $("#stats").innerHTML = "";
  $("#tab-table").innerHTML = `<p class="note">No results published yet, or they could not be loaded (${esc(e.message || e)}). The first table is coming soon.</p>`;
});

function init(data) {
  D = data;
  LIBS = D.libs;
  const F = Object.fromEntries(D.row_fields.map((f, i) => [f, i]));
  ROWS = D.rows.map(r => Object.fromEntries(Object.entries(F).map(([k, i]) => [k, r[i]])));
  for (const r of ROWS) {
    const k = key(r.lib, r.version, r.core, r.chip);
    if (!CELL.has(k)) CELL.set(k, []);
    CELL.get(k).push(r);
  }
  document.querySelectorAll(".baseline").forEach(e => e.textContent = D.baseline);
  document.querySelectorAll(".target").forEach(e => e.textContent = D.target);
  $("#corelist").textContent = D.cores.join(", ");
  $("#gen").textContent = `Data generated ${D.generated} · ${ROWS.length} compile results · ${D.cli_version}`;
  legend($("#legend")); legend($("#legend2"));
  stats();
  setupTable();
  renderRegressions();
  renderErrors();
  setupPin();
  renderNews();
  document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
  document.querySelectorAll("[data-goto]").forEach(a => a.onclick = e => {
    e.preventDefault(); showTab("about"); $("#" + a.dataset.goto).scrollIntoView({ behavior: "smooth" });
  });
  const h = location.hash.slice(1);
  if (h) showTab(h);
  $("#modal").onclick = e => { if (e.target.id === "modal" || e.target.classList.contains("close")) closeModal(); };
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });
}

function showTab(t) {
  if (!$("#tab-" + t)) return;
  document.querySelectorAll(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === t));
  document.querySelectorAll(".tab").forEach(s => s.classList.toggle("active", s.id === "tab-" + t));
  history.replaceState(null, "", "#" + t);
}

function key(li, v, core, chip) { return `${li}|${v}|${core}|${chip}`; }

// Per-example status: the default-options row, upgraded to pass_cfg when the huge_app retry compiled.
function examples(li, v, core, chip) {
  const rows = CELL.get(key(li, v, core, chip)) || [];
  const by = {};
  for (const r of rows) { (by[r.example] ||= {})[r.options ? "big" : "base"] = r; }
  return Object.entries(by).map(([ex, o]) => {
    const base = o.base || o.big;
    let s = base.status;
    if (o.base && !OK(o.base.status) && o.big && o.big.status === "pass") s = "pass_cfg";
    return { example: ex, status: s, base: o.base, big: o.big };
  });
}

function cell(li, v, core, chip) {
  const ex = examples(li, v, core, chip).map(e => e.status);
  if (!ex.length) return "none";
  const has = s => ex.includes(s);
  const anyOk = has("pass") || has("pass_cfg");
  if (has("fail")) return anyOk ? "partial" : "fail";
  if (has("dep_fail")) return anyOk ? "partial" : "dep_fail";
  if (anyOk) return has("pass") ? "pass" : "pass_cfg";
  if (has("config")) return "config";
  if (has("n/a")) return "n/a";
  return "infra_error";
}

// Regression: an example that compiled on the baseline core fails on the target core (same lib version, same chip).
function regressions(li, v, chip) {
  const base = Object.fromEntries(examples(li, v, D.baseline, chip).map(e => [e.example, e]));
  return examples(li, v, D.target, chip).filter(e => BAD(e.status) && base[e.example] && OK(base[e.example].status))
    .map(e => ({ ...e, before: base[e.example] }));
}
// Hardware note: every failing example in the cell failed on a peripheral this chip does not have.
function hwNote(li, v, core, chip) {
  const bad = examples(li, v, core, chip).filter(e => BAD(e.status)).map(e => e.base || e.big);
  return bad.length && bad.every(r => r.note) ? bad[0].note : "";
}
function hasRegression(li, v) { return D.chips.some(c => regressions(li, v, c).length); }

function badge(s, extra = "", attrs = "", note = "") {
  const [sym, cls, title] = SYM[s] || SYM.none;
  return `<span class="s ${cls} ${extra}" title="${esc(note ? title + " — " + note : title)}" ${attrs}>${sym}</span>`;
}

function legend(el) {
  el.innerHTML = ["pass", "pass_cfg", "partial", "fail", "dep_fail", "n/a", "config", "infra_error", "none"]
    .map(s => `<span>${badge(s)} ${esc(SYM[s][2])}</span>`).join("") +
    `<span>${badge("fail", "regr")} Broke on ${esc(D.target)} (compiled on ${esc(D.baseline)})</span>` +
    `<span>${badge("fail", "hw")} Expected: this chip lacks the hardware the example uses</span>`;
}

function tested(li) { return LIBS[li].versions.some(v => D.cores.some(c => D.chips.some(ch => CELL.has(key(li, v, c, ch))))); }

function stats() {
  const libsTested = LIBS.filter((_, i) => tested(i)).length;
  let p = 0, t = 0, reg = 0;
  LIBS.forEach((l, i) => {
    const v = l.versions[0];
    D.chips.forEach(ch => { const s = cell(i, v, D.target, ch); if (s !== "none" && s !== "infra_error") { t++; if (OK(s)) p++; } });
    if (hasRegression(i, v)) reg++;
  });
  $("#stats").innerHTML = `
    <div class="stat"><b>${libsTested}</b><span>libraries tested</span></div>
    <div class="stat"><b>${ROWS.length.toLocaleString()}</b><span>compiles, each with a log</span></div>
    <div class="stat"><b>${t ? Math.round(100 * p / t) : 0}%</b><span>newest versions that build on ${esc(D.target)}</span></div>
    <div class="stat bad"><b>${reg}</b><span>libraries broken by ${esc(D.target)}</span></div>`;
}

// ---------------- table ----------------
function setupTable() {
  const cats = [...new Set(LIBS.map(l => l.category))].sort();
  $("#cat").innerHTML += cats.map(c => `<option>${esc(c)}</option>`).join("");
  $("#chipf").innerHTML += D.chips.map(c => `<option value="${c}">${CHIP_NAME[c] || c}</option>`).join("");
  ["#q", "#cat", "#chipf", "#onlyreg", "#allver"].forEach(s => $(s).addEventListener("input", renderTable));
  renderTable();
}

function renderTable() {
  const q = $("#q").value.trim().toLowerCase(), cat = $("#cat").value, chipf = $("#chipf").value;
  const onlyreg = $("#onlyreg").checked, allver = $("#allver").checked;
  const chips = chipf ? [chipf] : D.chips;
  const cores = [...D.cores].reverse();   // newest core first
  let h = `<thead><tr><th rowspan="2">Library</th><th rowspan="2">Version</th>` +
    cores.map(c => `<th class="core" colspan="${chips.length}">core ${esc(c)}</th>`).join("") + `</tr><tr>` +
    cores.map(() => chips.map(ch => `<th class="chip">${CHIP_NAME[ch] || ch}</th>`).join("")).join("") + `</tr></thead><tbody>`;
  const order = LIBS.map((l, i) => i).filter(tested).sort((a, b) => LIBS[a].name.localeCompare(LIBS[b].name, undefined, { sensitivity: "base" }));
  let shown = 0;
  for (const li of order) {
    const l = LIBS[li];
    if (q && !l.name.toLowerCase().includes(q)) continue;
    if (cat && l.category !== cat) continue;
    const vers = allver ? l.versions : [l.versions[0]];
    if (onlyreg && !vers.some(v => hasRegression(li, v))) continue;
    vers.forEach((v, vi) => {
      const regChips = new Set(chips.filter(ch => regressions(li, v, ch).length));
      h += `<tr class="${vi ? "older" : ""}"><td class="lib">` +
        (vi ? "" : `<a href="${esc(l.repo)}" target="_blank" rel="noopener">${esc(l.name)}</a>` +
          (l.espressif_tested ? `<span class="tag" title="Also compiled by Espressif's own CI">Espressif CI</span>` : "") +
          (l.note ? `<span class="tag note" title="${esc(l.note)}">note</span>` : "")) +
        (regChips.size ? `<span class="tag reg">broken on ${esc(D.target)}</span>` : "") +
        `</td><td class="ver">${esc(v)}</td>`;
      cores.forEach(core => chips.forEach((ch, ci) => {
        const s = cell(li, v, core, ch);
        const regr = core === D.target && regChips.has(ch) ? "regr" : "";
        const hw = BAD(s) || s === "partial" ? hwNote(li, v, core, ch) : "";
        const attrs = (s === "none" ? "" : `tabindex="0" data-cell="${li}|${esc(v)}|${core}|${ch}"`) +
          (hw ? ` data-hw="1"` : "");
        h += `<td class="c ${ci === 0 ? "first" : ""}">${badge(s, regr + (hw ? " hw" : ""), attrs, hw)}</td>`;
      }));
      h += `</tr>`;
    });
    shown++;
  }
  h += `</tbody>`;
  if (!shown) h = `<tbody><tr><td class="muted">No libraries match.</td></tr></tbody>`;
  const t = $("#grid");
  t.innerHTML = h;
  t.querySelectorAll("[data-cell]").forEach(el => {
    const open = () => { const [li, v, core, ch] = el.dataset.cell.split("|"); showCell(+li, v, core, ch); };
    el.onclick = open;
    el.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } };
  });
}

function exHtml(e) {
  const rows = [e.base, e.big].filter(Boolean);
  return rows.map(r => `
    <div class="ex">
      ${badge(r.status)} <b>${esc(r.example)}</b> ${r.options ? `<span class="tag">${esc(r.options)}</span>` : ""}
      ${r.first_error ? `<div class="err">${esc(r.first_error)}</div>` : ""}
      ${r.note ? `<div class="hwnote">${esc(r.note)}</div>` : ""}
      <div class="meta">${r.root_cause ? esc(r.root_cause) + " · " : ""}<a href="${BASE}logs/${esc(r.log)}" target="_blank" rel="noopener">compile log</a>
        · tested ${esc(r.date)}${Object.keys(r.deps || {}).length ? " · with " + Object.entries(r.deps).map(([n, v]) => esc(n) + " " + esc(v)).join(", ") : ""}</div>
    </div>`).join("");
}

function showCell(li, v, core, chip) {
  const l = LIBS[li];
  const exs = examples(li, v, core, chip);
  const reg = core === D.target ? regressions(li, v, chip) : [];
  let h = `<h2>${esc(l.name)} ${esc(v)}</h2><p class="muted">core ${esc(core)} · ${CHIP_NAME[chip] || chip} · ${badge(cell(li, v, core, chip))} ${esc(SYM[cell(li, v, core, chip)][2])}</p>`;
  if (reg.length) h += `<p><span class="tag reg">broken on ${esc(D.target)}</span> These examples compiled on core ${esc(D.baseline)}: ` +
    reg.map(r => `<a href="${BASE}logs/${esc((r.before.base || r.before.big).log)}" target="_blank" rel="noopener">${esc(r.example)} on ${esc(D.baseline)}</a>`).join(", ") + `</p>`;
  if (l.note) h += `<p class="libnote"><b>Note:</b> ${esc(l.note)}</p>`;
  h += exs.map(exHtml).join("");
  if (l.risk_reasons?.length) h += `<p class="muted" style="margin-top:12px">Why we expected risk: ${esc(l.risk_reasons.join("; "))}.</p>`;
  openModal(h);
}
function openModal(h) { $("#modal-body").innerHTML = h; $("#modal").hidden = false; $(".modal .close").focus(); }
function closeModal() { $("#modal").hidden = true; }

// ---------------- what's new (written by the farm's nightly report) ----------------
const NEWS_ICON = { core: "🆕", release: "📦", broken: "⚠️", fixed: "✅" };
function renderNews() {
  const news = D.news || [];
  if (!news.length) return;
  const el = $("#news");
  const item = n => `<li><span class="muted">${esc(n.date)}</span> ${NEWS_ICON[n.kind] || "•"} ${esc(n.text)}</li>`;
  el.innerHTML = `<b>What's new</b><ul>${news.slice(0, 4).map(item).join("")}</ul>` +
    (news.length > 4 ? `<details><summary>Older updates</summary><ul>${news.slice(4).map(item).join("")}</ul></details>` : "");
  el.hidden = false;
}

// ---------------- regressions ----------------
function renderRegressions() {
  const out = [];
  LIBS.forEach((l, li) => {
    l.versions.forEach((v, vi) => {
      const per = D.chips.map(ch => [ch, regressions(li, v, ch)]).filter(([, r]) => r.length);
      if (!per.length) return;
      const first = per[0][1][0].base || per[0][1][0].big;
      out.push({ l, li, v, vi, per, first });
    });
  });
  out.sort((a, b) => a.vi - b.vi || a.l.name.localeCompare(b.l.name));
  $("#reglist").innerHTML = out.length ? out.map(o => `
    <div class="card">
      <h3>${esc(o.l.name)} <span class="ver">${esc(o.v)}${o.vi === 0 ? " (newest)" : ""}</span></h3>
      <div class="muted">Broken on ${o.per.map(([ch]) => CHIP_NAME[ch] || ch).join(", ")} · ${esc(o.first.root_cause)}</div>
      <div class="err">${esc(o.first.first_error)}</div>
      <div class="meta muted" style="font-size:13px">Logs: ${o.per.map(([ch, rs]) => rs.map(r => {
        const b = r.before.base || r.before.big, a = r.base || r.big;
        return `${CHIP_NAME[ch] || ch} ${esc(r.example)}: <a href="${BASE}logs/${esc(b.log)}" target="_blank" rel="noopener">${esc(D.baseline)} ✓</a> → <a href="${BASE}logs/${esc(a.log)}" target="_blank" rel="noopener">${esc(D.target)} ✗</a>`;
      }).join(" · ")).join(" · ")}</div>
    </div>`).join("") : `<p class="muted">No regressions found yet.</p>`;
}

// ---------------- error groups ----------------
function normErr(s) { return (s || "").replace(/(?:[A-Za-z]:)?[\\/][^\s'"`:]+[\\/]/g, "").replace(/\b\d+\b/g, "N").trim(); }

function renderErrors() {
  const groups = {};
  for (const r of ROWS) {
    if (r.core !== D.target || !BAD(r.status) || r.options) continue;
    const g = groups[r.root_cause || "Other"] ||= { libs: new Set(), msgs: {}, n: 0 };
    g.n++; g.libs.add(r.lib);
    const m = g.msgs[normErr(r.first_error)] ||= { libs: new Map(), log: r.log };
    m.libs.set(LIBS[r.lib].name + " " + r.version, r.log);
  }
  const sorted = Object.entries(groups).sort((a, b) => b[1].libs.size - a[1].libs.size);
  $("#errgroups").innerHTML = sorted.length ? sorted.map(([label, g]) => `
    <details class="card">
      <summary class="group-h"><b>${esc(label)}</b><span class="count">${g.libs.size} libraries · ${g.n} compiles</span></summary>
      ${Object.entries(g.msgs).sort((a, b) => b[1].libs.size - a[1].libs.size).map(([msg, m]) => `
        <div class="ex"><div class="err">${esc(msg)}</div>
        <div class="meta">${[...m.libs].map(([name, log]) => `<a href="${BASE}logs/${esc(log)}" target="_blank" rel="noopener">${esc(name)}</a>`).join(", ")}</div></div>`).join("")}
    </details>`).join("") : `<p class="muted">No failures on ${esc(D.target)} yet.</p>`;
}

// ---------------- pin tool ----------------
function setupPin() {
  $("#pchip").innerHTML = D.chips.map(c => `<option value="${c}">${CHIP_NAME[c] || c}</option>`).join("");
  $("#pcore").innerHTML = [...D.cores].reverse().map(c => `<option>${esc(c)}</option>`).join("");
  const order = LIBS.map((l, i) => i).filter(tested).sort((a, b) => LIBS[a].name.localeCompare(LIBS[b].name, undefined, { sensitivity: "base" }));
  $("#plibs").innerHTML = order.map(li => `<label data-name="${esc(LIBS[li].name.toLowerCase())}"><input type="checkbox" value="${li}"> ${esc(LIBS[li].name)}</label>`).join("");
  $("#pq").oninput = () => {
    const q = $("#pq").value.toLowerCase();
    $("#plibs").querySelectorAll("label").forEach(l => l.hidden = q && !l.dataset.name.includes(q));
  };
  ["#pchip", "#pcore"].forEach(s => $(s).onchange = renderPin);
  $("#plibs").onchange = renderPin;
}

function pickVersion(li, core, chip) {
  for (const v of LIBS[li].versions) {
    const s = cell(li, v, core, chip);
    if (OK(s)) {
      const deps = {}; const opts = new Set();
      for (const e of examples(li, v, core, chip)) {
        if (!OK(e.status)) continue;
        const r = e.status === "pass_cfg" ? e.big : e.base;
        Object.assign(deps, r.deps || {});
        if (e.status === "pass_cfg") r.options.split(",").forEach(o => opts.add(o));
      }
      return { v, s, deps, opts: [...opts] };
    }
  }
  return null;
}

function renderPin() {
  const chip = $("#pchip").value, core = $("#pcore").value;
  const sel = [...$("#plibs").querySelectorAll("input:checked")].map(i => +i.value);
  const out = $("#pout");
  if (!sel.length) { out.innerHTML = `<p class="muted">Select one or more libraries.</p>`; return; }
  const picks = sel.map(li => ({ li, p: pickVersion(li, core, chip) }));
  const missing = picks.filter(x => !x.p);
  const bestCore = [...D.cores].reverse().find(c => sel.every(li => pickVersion(li, c, chip)));
  let h = `<table><thead><tr><th>Library</th><th>Pin to</th><th>Result on core ${esc(core)} / ${CHIP_NAME[chip] || chip}</th></tr></thead><tbody>`;
  for (const { li, p } of picks) {
    const l = LIBS[li];
    if (p) {
      const newest = l.versions[0] === p.v;
      h += `<tr><td>${esc(l.name)}</td><td><b>${esc(p.v)}</b></td><td>${badge(p.s)} ${newest ? "newest version compiles" : `newest tested version (${esc(l.versions[0])}) does not; ${esc(p.v)} does`}${p.opts.length ? " · needs board options " + esc(p.opts.join(",")) : ""}</td></tr>`;
    } else {
      h += `<tr><td>${esc(l.name)}</td><td>—</td><td>${badge(cell(li, l.versions[0], core, chip))} no tested version compiles on this core and chip</td></tr>`;
    }
  }
  h += `</tbody></table>`;
  if (missing.length) {
    h += bestCore ? `<p><b>Suggestion:</b> every selected library has a version that compiles on core <b>${esc(bestCore)}</b> for ${CHIP_NAME[chip] || chip}. Switch the core above to get a complete lockfile.</p>`
      : `<p><b>No tested core</b> builds all selected libraries for ${CHIP_NAME[chip] || chip}. Remove a library or try another chip.</p>`;
  }
  const ok = picks.filter(x => x.p);
  if (ok.length) {
    const all = {};
    for (const { li, p } of ok) Object.assign(all, p.deps);
    for (const { li, p } of ok) all[LIBS[li].name] = p.v;
    const opts = [...new Set(ok.flatMap(x => x.p.opts))];
    const big = opts.includes(D.big_app_option);
    const fqbn = `esp32:esp32:${chip}${opts.length ? ":" + opts.join(",") : ""}`;
    const libsSorted = Object.entries(all).sort((a, b) => a[0].localeCompare(b[0]));
    const yaml = `profiles:\n  ${chip}:\n    fqbn: ${fqbn}\n    platforms:\n      - platform: esp32:esp32 (${core})\n        platform_index_url: https://espressif.github.io/arduino-esp32/package_esp32_index.json\n    libraries:\n` +
      libsSorted.map(([n, v]) => `      - ${n} (${v})`).join("\n") + `\n`;
    const pio = `; PlatformIO: use a platform that ships Arduino-ESP32 core ${core}\n; (for core 3.x and 4.x that is the community "pioarduino" platform)\n[env:${chip}]\nframework = arduino\n` +
      (big ? `board_build.partitions = huge_app.csv\n` : "") +
      (opts.includes("USBMode=default") ? `build_flags = -DARDUINO_USB_MODE=0   ; USB-OTG (TinyUSB)\n` : "") + `lib_deps =\n` + libsSorted.map(([n, v]) => `    ${n} @ ${v}`).join("\n") + `\n`;
    h += `<h3>sketch.yaml <span><button class="copy" data-t="y">Copy</button></span></h3><pre id="py">${esc(yaml)}</pre>
      <p class="muted">Save next to your .ino file and build with <code>arduino-cli compile --profile ${esc(chip)}</code>. It also pins the helper libraries our test used.</p>
      <h3>platformio.ini <span><button class="copy" data-t="p">Copy</button></span></h3><pre id="pp">${esc(pio)}</pre>`;
  }
  out.innerHTML = h;
  out.querySelectorAll(".copy").forEach(b => b.onclick = () => {
    navigator.clipboard?.writeText($(b.dataset.t === "y" ? "#py" : "#pp").textContent);
    b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1200);
  });
}
