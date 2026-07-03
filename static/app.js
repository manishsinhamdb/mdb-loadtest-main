"use strict";

const $ = (id) => document.getElementById(id);
const j = (el, obj) => { el.textContent = (typeof obj === "string") ? obj : JSON.stringify(obj, null, 2); };

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, data };
}

// db-name lives on the Output Details tab but is read from anywhere (single SPA).
function connFields() {
  return {
    uri: $("uri").value.trim(),
    auth_source: $("auth-source").value.trim() || null,
    default_db: $("db-name").value.trim() || null,
  };
}

// ---- tabs ------------------------------------------------------------------
const TABS = ["connection", "output", "workloads"];
let activeTab = 0;
function showTab(idx) {
  activeTab = Math.max(0, Math.min(TABS.length - 1, idx));
  const name = TABS[activeTab];
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
  $("btn-prev").disabled = (activeTab === 0);
  $("btn-next").disabled = (activeTab === TABS.length - 1);
  window.scrollTo({ top: 0 });
}

// ---- theme switcher --------------------------------------------------------
const NEON_CYCLE = ["#34d8e8", "#00ED64", "#facc15", "#a78bfa", "#fb7185", "#e8eef7"];
function applyNeon(color) {
  document.documentElement.style.setProperty("--neon", color);
  try { localStorage.setItem("loadgen_neon", color); } catch (e) {}
}
function setupTheme() {
  let saved = null;
  try { saved = localStorage.getItem("loadgen_neon"); } catch (e) {}
  applyNeon(saved && NEON_CYCLE.includes(saved) ? saved : NEON_CYCLE[0]);
  $("theme-btn").addEventListener("click", () => {
    const cur = getComputedStyle(document.documentElement).getPropertyValue("--neon").trim();
    let i = NEON_CYCLE.findIndex((c) => c.toLowerCase() === cur.toLowerCase());
    applyNeon(NEON_CYCLE[(i + 1) % NEON_CYCLE.length]);
  });
}

// ---- workload catalog -> UI ------------------------------------------------
function renderWorkloads(list) {
  const box = $("workloads");
  box.innerHTML = "";
  list.forEach((w, idx) => {
    const div = document.createElement("div");
    div.className = "wl";
    div.dataset.key = w.key;
    const params = w.default_params || {};
    const paramInputs = Object.entries(params).map(([k, v]) => {
      const val = (v === null || v === undefined) ? "" : v;
      const type = (typeof v === "number") ? "number" : "text";
      return `<div><label>${k}</label><input data-param="${k}" type="${type}" value="${val}" /></div>`;
    }).join("");
    div.innerHTML = `
      <div class="wl-head">
        <input type="checkbox" class="wl-enable" />
        <span class="name">${idx + 1}. ${w.label}</span>
        <span class="key">${w.key}</span>
      </div>
      <div class="wl-params">${paramInputs || '<small>no parameters</small>'}</div>`;
    const cb = div.querySelector(".wl-enable");
    cb.addEventListener("change", () => div.classList.toggle("active", cb.checked));
    box.appendChild(div);
  });
}

function renderCollections(list, counts) {
  const box = $("collections");
  box.innerHTML = "";
  (list || []).forEach((c) => {
    const cnt = counts && (c.name in counts) ? `${counts[c.name].toLocaleString()} docs` : "";
    const d = document.createElement("div");
    d.className = "coll";
    d.innerHTML = `<span class="cnt">${cnt}</span><div class="nm">${c.name}</div>`
                + `<div>${c.role}</div><div class="ix">indexes: ${c.indexes}</div>`;
    box.appendChild(d);
  });
}

function selectedWorkloads() {
  const out = {};
  document.querySelectorAll(".wl").forEach((div) => {
    const cb = div.querySelector(".wl-enable");
    if (!cb.checked) return;
    const params = {};
    div.querySelectorAll("[data-param]").forEach((inp) => {
      const k = inp.dataset.param;
      let v = inp.value;
      if (inp.type === "number") v = (v === "" ? null : Number(v));
      else if (v === "") v = null;
      params[k] = v;
    });
    out[div.dataset.key] = params;
  });
  return out;
}

// ---- clock ----------------------------------------------------------------
function tickClock() {
  const now = new Date();
  $("clk-utc").textContent = now.toISOString().replace("T", " ").slice(0, 19) + "Z";
  $("clk-ist").textContent = now.toLocaleString("en-GB", { timeZone: "Asia/Kolkata", hour12: false });
}

// ---- log poller -----------------------------------------------------------
let lastSeq = 0;
async function pollLogs() {
  try {
    const { data } = await api("GET", `/api/logs?since=${lastSeq}`);
    const box = $("log");
    (data.logs || []).forEach((r) => {
      lastSeq = Math.max(lastSeq, r.seq);
      const line = document.createElement("div");
      line.className = "ln " + r.level;
      line.textContent = `[${r.ist} IST] ${r.level} ${r.msg}`;
      box.appendChild(line);
    });
    if (data.logs && data.logs.length) box.scrollTop = box.scrollHeight;
  } catch (e) { /* ignore transient */ }
}

let COLLECTIONS = [];
let PERSIST_BACKEND = "OS scheduler";

// ---- handlers -------------------------------------------------------------
function setupHandlers() {
  document.querySelectorAll(".tab-btn").forEach((b) =>
    b.addEventListener("click", () => showTab(TABS.indexOf(b.dataset.tab))));
  $("btn-prev").addEventListener("click", () => showTab(activeTab - 1));
  $("btn-next").addEventListener("click", () => showTab(activeTab + 1));

  $("toggle-uri").addEventListener("click", () => {
    const f = $("uri");
    f.type = f.type === "password" ? "text" : "password";
    $("toggle-uri").textContent = f.type === "password" ? "Show" : "Hide";
  });

  $("btn-test").addEventListener("click", async () => {
    const el = $("conn-result"); j(el, "Testing…");
    const { data } = await api("POST", "/api/test-connection", connFields());
    const c = data.connection || {};
    let html = "";
    if (c.ok) {
      html += `CONNECTION OK\n  version: ${c.server_version}\n  topology: ${c.topology}\n`
            + `  primary: ${c.is_primary}\n  edition: ${c.edition}  modules: ${JSON.stringify(c.modules)}\n`
            + `  target: ${c.target.redacted_uri}\n  db: ${data.db}\n\n`;
      const perm = data.permission || {};
      html += `PERMISSION CHECK on '${perm.db}': ${perm.ok ? "ALL PASS ✓" : "FAILED ✗"}\n`;
      (perm.capabilities || []).forEach((cap) => {
        html += `  ${cap.pass ? "PASS" : "FAIL"}  ${cap.name}${cap.pass ? "" : "  -> " + cap.detail}\n`;
      });
      const sk = data.clock_skew || {};
      html += `\nCLOCK SKEW: ${sk.skew_seconds}s  ${sk.ok ? "OK" : "WARN — " + (sk.warning || "")}\n`;
    } else {
      const e = c.error || {};
      html += `CONNECTION FAILED\n  cause: ${e.cause}\n  hint: ${e.hint}\n  raw: ${e.message}`;
    }
    if (c.target) $("uri-redacted").textContent = c.target.redacted_uri;
    j(el, html);
  });

  $("btn-output").addEventListener("click", async () => {
    const { data } = await api("POST", "/api/check-output", { path: $("output-dir").value.trim() });
    j($("output-result"), data.ok ? `OK — writable: ${data.path}` : `FAIL — ${data.error}`);
  });

  $("btn-seed").addEventListener("click", async () => {
    const cf = connFields();
    const body = { ...cf,
      large_count: Number($("seed-large").value), agg_count: Number($("seed-agg").value),
      hot_docs: Number($("seed-hot").value),
      seed: $("seed-seed").value === "" ? null : Number($("seed-seed").value) };
    const { data } = await api("POST", "/api/seed", body);
    j($("seed-result"), data.error ? data.error : "Seeding started… (watch the log)");
    pollSeed();
  });

  $("btn-run").addEventListener("click", async () => {
    const cf = connFields();
    const wl = selectedWorkloads();
    if (Object.keys(wl).length === 0) { j($("run-result"), "Select at least one workload."); return; }
    const body = { ...cf,
      output_dir: $("output-dir").value.trim(),
      duration_seconds: Number($("run-duration").value),
      seed: $("run-seed").value === "" ? null : Number($("run-seed").value),
      workloads: wl,
      auto_seed: $("run-autoseed").checked,
      seed_params: { large_count: Number($("seed-large").value), agg_count: Number($("seed-agg").value),
                     hot_docs: Number($("seed-hot").value) },
      ignore_skew: $("run-ignoreskew").checked };
    const { data } = await api("POST", "/api/run", body);
    if (!data.run_id) { j($("run-result"), data); return; }
    $("run-status").textContent = "running…";
    pollRun(data.run_id);
  });

  $("sch-mode").addEventListener("change", updateSchNote);

  $("btn-schedule").addEventListener("click", async () => {
    const cf = connFields();
    const mode = $("sch-mode").value;
    if (mode === "permanent") {
      const body = { ...cf,
        output_dir: $("output-dir").value.trim(),
        duration_seconds: Number($("sch-duration").value),
        start_ist: $("sch-start").value.trim(),
        days: Number($("sch-days").value), base_seed: Number($("sch-seed").value),
        random_delay_min: Number($("sch-jitter").value),
        seed_large: Number($("seed-large").value), seed_agg: Number($("seed-agg").value),
        seed_hot: Number($("seed-hot").value) };
      const { data } = await api("POST", "/api/persistent-schedule", body);
      j($("schedule-result"), data.ok
        ? `PERMANENT task '${data.task_name}' registered.\n  next run: ${data.next_run || "(pending)"}\n  ${data.note}`
        : `FAILED: ${data.error}`);
    } else {
      const body = { ...cf,
        output_dir: $("output-dir").value.trim(),
        duration_seconds: Number($("sch-duration").value),
        start_ist: $("sch-start").value.trim(), end_ist: $("sch-end").value.trim(),
        days: Number($("sch-days").value), base_seed: Number($("sch-seed").value),
        workloads: selectedWorkloads() };
      const { data } = await api("POST", "/api/schedule", body);
      j($("schedule-result"), data);
    }
    listSchedule();
  });

  $("btn-sched-list").addEventListener("click", listSchedule);

  $("btn-sched-remove").addEventListener("click", async () => {
    if (!confirm("Remove the permanent Windows scheduled task?")) return;
    const { data } = await api("DELETE", "/api/persistent-schedule");
    j($("schedule-result"), data.ok ? `Removed permanent task '${data.task_name}'.` : `Could not remove: ${data.detail}`);
    listSchedule();
  });

  $("btn-teardown").addEventListener("click", async () => {
    if (!confirm("Drop the load-test database and remove ALL scheduled jobs?")) return;
    const cf = connFields();
    const { data } = await api("POST", "/api/teardown", { ...cf, drop_db: true, remove_jobs: true });
    j($("teardown-result"), data);
  });
}

async function pollSeed() {
  const { data } = await api("GET", "/api/seed");
  if (data.running) { j($("seed-result"), "Seeding in progress…"); setTimeout(pollSeed, 1500); }
  else if (data.error) j($("seed-result"), "FAILED: " + data.error);
  else if (data.result) {
    j($("seed-result"), data.result);
    const counts = {};
    (data.result.collections || []).forEach((c) => { counts[c.collection] = c.count; });
    renderCollections(COLLECTIONS, counts);
  }
}

async function pollRun(runId) {
  const { data } = await api("GET", `/api/run/${runId}`);
  $("run-status").textContent = `${data.status} (${data.phase || ""})`;
  if (data.status === "done") { j($("run-result"), data.summary); }
  else if (data.status === "failed") { j($("run-result"), "FAILED — " + data.error); }
  else { j($("run-result"), `status: ${data.status}\nphase: ${data.phase}`); setTimeout(() => pollRun(runId), 1500); }
}

function updateSchNote() {
  const mode = $("sch-mode").value;
  $("sch-note").textContent = (mode === "permanent")
    ? `Permanent: registers an OS task (${PERSIST_BACKEND}) that runs run_window.py daily at the start `
      + "time (+jitter). Survives reboot and runs with this app closed; it runs when you are logged on "
      + "(cannot run while fully logged off). Auto-seeds before each run."
    : "In-app: APScheduler fires the run, but ONLY while this web app is running. Persisted in SQLite so "
      + "the job survives an app restart, but it will not fire if the app is stopped.";
}

async function listSchedule() {
  let s = "";
  const inapp = (await api("GET", "/api/schedule")).data;
  s += "IN-APP (needs app running):\n";
  if (!inapp.jobs || !inapp.jobs.length) s += "  none\n";
  else inapp.jobs.forEach((jb) => {
    s += `  ${jb.job_id}\n    next: ${jb.next_run_time ? jb.next_run_time.ist + " IST" : "(none)"}\n    ${jb.trigger}\n`;
  });
  const perm = (await api("GET", "/api/persistent-schedule")).data;
  s += "\nPERMANENT (Windows Task Scheduler):\n";
  if (!perm.tasks || !perm.tasks.length) s += "  none\n";
  else perm.tasks.forEach((t) => {
    s += `  ${t.task_name}  [${t.state}]\n    next: ${t.next_run || "(pending)"}\n`
       + `    last: ${t.last_run || "(never)"}  result: ${t.last_result}\n`;
  });
  j($("schedule-result"), s);
}

// ---- boot -----------------------------------------------------------------
(async function boot() {
  setupTheme();
  const { data } = await api("GET", "/api/catalog");
  renderWorkloads(data.workloads || []);
  COLLECTIONS = data.collections || [];
  renderCollections(COLLECTIONS, null);
  $("output-dir").value = data.defaults.output_dir;
  $("db-name").value = data.defaults.db;
  if (data.defaults.persistent_backend) PERSIST_BACKEND = data.defaults.persistent_backend;
  setupHandlers();
  updateSchNote();
  showTab(0);
  tickClock(); setInterval(tickClock, 1000);
  pollLogs(); setInterval(pollLogs, 1500);
  listSchedule();
})();
