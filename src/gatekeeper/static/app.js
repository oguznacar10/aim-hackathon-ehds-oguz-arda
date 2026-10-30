"use strict";

const ARTICLES = {
  "53": "Lists the purposes health data may be reused for, such as research, public health and official statistics.",
  "54": "Forbids uses such as decisions that harm people, insurance or job discrimination, advertising and harmful products.",
  "66": "Data must be anonymised by default; pseudonymised data only when the applicant shows anonymised data cannot serve the purpose.",
  "67": "Sets out what a data access application has to contain.",
  "68": "Access to pseudonymised data needs a data permit and happens only inside a secure processing environment.",
  "69": "A health data request is answered with anonymised statistics only; the applicant never sees the data.",
  "71": "People may opt out of the reuse of their health data; their records are left out.",
  "73": "The secure processing environment: only non-personal results may leave it.",
};
const VERDICT = {
  REJECT: "Refused: the purpose is not allowed",
  APPROVE_STATISTICAL: "Approved: anonymised statistics",
  APPROVE_SPE: "Approved: records in a secure processing environment",
};
const STEPS = [
  "Is the purpose prohibited?",
  "Is it a request for statistics only?",
  "Does the application explain why statistics are not enough?",
  "Otherwise: answer with statistics",
];
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let examples = [];

const $ = (sel, root = document) => root.querySelector(sel);
function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (v !== false && v != null) node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) node.append(kid);
  return node;
}
async function api(path, options = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}
function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
function label(key) {
  const words = key.replace(/_pct$/, "").replace(/^pct_/, "").split("_").join(" ");
  const pct = /(^pct_|_pct$)/.test(key) ? " (%)" : "";
  const text = key.startsWith("pct_") ? `Share ${words}` : words;
  return text.charAt(0).toUpperCase() + text.slice(1) + pct;
}

/* views */
document.querySelectorAll(".view-btn").forEach((btn) => btn.addEventListener("click", () => {
  document.querySelectorAll(".view-btn").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== btn.dataset.view; });
  if (btn.dataset.view === "staff") loadQueue();
}));

/* intake */
async function loadExamples() {
  const res = await api("/api/examples");
  examples = res.body || [];
  const select = $("#example");
  for (const ex of examples) {
    select.append(el("option", { value: ex.id, text: `${ex.id}  ${ex.applicant.organisation}` }));
  }
}
$("#example").addEventListener("change", (e) => {
  const ex = examples.find((x) => x.id === e.target.value);
  if (!ex) return;
  const f = $("#request-form");
  f.name.value = ex.applicant.name || "";
  f.organisation.value = ex.applicant.organisation || "";
  f.country.value = ex.applicant.country || "";
  f.id.value = ex.id;
  f.querySelector(`input[name=requested_as][value="${ex.requested_as}"]`).checked = true;
  f.purpose.value = ex.purpose;
  f.question.value = ex.question;
  f.definitions.value = (ex.definitions || []).join("\n");
});

function readForm() {
  const f = $("#request-form");
  const ex = examples.find((x) => x.id === f.id.value.trim());
  return {
    id: f.id.value.trim(),
    submitted: ex ? ex.submitted : new Date().toISOString(),
    applicant: { name: f.name.value.trim(), organisation: f.organisation.value.trim(), country: f.country.value.trim().toUpperCase() },
    requested_as: f.querySelector("input[name=requested_as]:checked").value,
    requested_format: ex ? ex.requested_format : "",
    purpose: f.purpose.value.trim(),
    question: f.question.value.trim(),
    definitions: f.definitions.value.split("\n").map((s) => s.trim()).filter(Boolean),
  };
}

$("#request-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const error = $("#form-error");
  const request = readForm();
  const missing = [["id", "Case number"], ["purpose", "Purpose"], ["question", "Question"]].find(([k]) => !request[k]);
  if (missing) {
    error.textContent = `${missing[1]} is empty. Fill it in and submit again.`;
    error.hidden = false;
    return;
  }
  error.hidden = true;
  const btn = $("#submit");
  btn.disabled = true;
  btn.textContent = "Deciding...";
  const slot = $("#notice-slot");
  slot.replaceChildren(pendingNotice(request));
  const res = await api("/api/decide", { method: "POST", body: JSON.stringify(request) });
  btn.disabled = false;
  btn.textContent = "Submit request";
  if (!res.ok) {
    slot.replaceChildren();
    error.textContent = res.body.error || `The server answered ${res.status}.`;
    error.hidden = false;
    return;
  }
  const notice = renderNotice(request, res.body);
  slot.replaceChildren(notice);
  animatePath(notice, res.body.rule);
});

function pendingNotice(request) {
  const n = $("#notice-tpl").content.firstElementChild.cloneNode(true);
  $(".case-no", n).textContent = request.id;
  $(".applicant", n).textContent = request.applicant.organisation;
  $(".verdict", n).textContent = "Deciding";
  $(".verdict-code", n).hidden = true;
  const ol = $(".path", n);
  ol.classList.add("pending");
  STEPS.forEach((s, i) => ol.append(el("li", {}, el("span", { class: "n", text: String(i + 1) }), el("span", { text: s }), el("span", { class: "answer" }))));
  $(".reasons-wrap", n).hidden = true;
  return n;
}

/* the notice */
function stepAnswers(result, request) {
  const r = result.rule;
  const isApp = request.requested_as === "health data access application";
  return STEPS.map((_, i) => {
    const step = i + 1;
    if (step < r) {
      const answer = step === 3 ? "No" : step === 2 ? "No, records were asked for" : "No";
      return { state: "checked", answer };
    }
    if (step === r) {
      const answer = { 1: "Yes: refused", 2: "Yes: statistics", 3: "Yes: secure environment", 4: isApp ? "Records not justified: statistics instead" : "Statistics" }[step];
      return { state: "decisive", answer };
    }
    return { state: "unreached", answer: "Not reached" };
  });
}

function renderNotice(request, result) {
  const n = $("#notice-tpl").content.firstElementChild.cloneNode(true);
  n.classList.add(`d-${result.decision}`);
  $(".case-no", n).textContent = result.id;
  $(".applicant", n).textContent = request.applicant.organisation;
  $(".date", n).textContent = fmtDate(request.submitted);
  $(".verdict", n).textContent = VERDICT[result.decision];
  $(".decision-code", n).textContent = result.decision;
  $(".review-flag", n).hidden = !result.needs_staff_review;

  const ol = $(".path", n);
  stepAnswers(result, request).forEach((s, i) => {
    const li = el("li", { class: s.state, "data-state": s.state },
      el("span", { class: "n", text: String(i + 1) }),
      el("span", { text: STEPS[i] }),
      el("span", { class: "answer", text: s.answer }));
    if (s.state === "decisive" && result.evidence) {
      li.append(el("p", { class: "quote", text: `"${result.evidence}"` }));
    }
    ol.append(li);
  });

  const reasons = $(".reasons", n);
  const sentences = result.reason.split(/(?<=[.;])\s+(?=[A-Z])/);
  for (const sentence of sentences.map((s) => s.trim()).filter(Boolean)) {
    const refs = [...new Set([...sentence.matchAll(/Art\. (\d+)(\(\w+\))?/g)].map((m) => m[0]))];
    const margin = el("div", { class: "margin" });
    for (const ref of refs) {
      const num = ref.match(/\d+/)[0];
      const note = el("p", { class: "art-note", hidden: "", text: ARTICLES[num] || "" });
      const btn = el("button", { type: "button", class: "art", "aria-expanded": "false", text: ref });
      btn.addEventListener("click", () => {
        const open = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!open));
        note.hidden = open;
      });
      margin.append(btn, note);
    }
    reasons.append(el("p", { text: sentence }), margin);
  }

  const outcome = $(".outcome", n);
  if (result.decision === "REJECT") {
    outcome.append(el("h3", { text: "What happens now" }),
      el("p", { class: "next-steps", text: "No data is released. You can submit a new request with a purpose listed in Art. 53, such as research or public health. You can also contest this decision before the national authority." }));
  } else if (result.decision === "APPROVE_STATISTICAL") {
    outcome.append(el("h3", { text: "Your statistics" }), statsTable(request, result.answer));
  } else {
    outcome.append(el("h3", { text: "Your secure processing environment" }), sealedRoom(result));
  }
  return n;
}

function animatePath(notice, rule) {
  const items = [...notice.querySelectorAll(".path li")];
  if (reduceMotion) return;
  items.forEach((li) => { li.dataset.final = li.className; li.className = "unreached"; li.querySelector(".answer").style.visibility = "hidden"; });
  items.forEach((li, i) => setTimeout(() => {
    li.className = li.dataset.final;
    li.querySelector(".answer").style.visibility = "";
  }, 120 * (Math.min(i, rule - 1) + 1)));
}

function statsTable(request, answer) {
  const wrap = el("div");
  wrap.append(el("p", { class: "caption", text: `${request.question} Opted-out patients are excluded. Reference date 31 December 2025.` }));
  const groups = Object.keys(answer || {});
  const flat = groups.length && typeof answer[groups[0]] !== "object";
  const rows = flat ? [["All", answer]] : groups.map((g) => [g, answer[g]]);
  const measures = Object.keys(rows[0] ? rows[0][1] : {});
  let masked = false;
  const table = el("table", { class: "stats" },
    el("thead", {}, el("tr", {}, el("th", { scope: "col", text: flat ? "" : "Group" }), measures.map((m) => el("th", { scope: "col", text: label(m) })))),
    el("tbody", {}, rows.map(([g, vals]) => el("tr", {}, el("th", { scope: "row", text: g }),
      measures.map((m) => {
        const v = vals[m];
        if (typeof v === "string") { masked = true; return el("td", {}, el("span", { class: "masked", title: "Hidden by the small-cell rule", text: `${v}*` })); }
        return el("td", { text: Number.isInteger(v) ? v.toLocaleString("en-GB") : v.toFixed(1) });
      })))));
  wrap.append(table);
  wrap.append(el("p", { class: "footnote", text: (masked ? "* " : "") + "Small-cell rule: counts under 10 are shown as <10, and percentages or means based on fewer than 10 patients as suppressed, so no person can be singled out. Every requested group is listed, even when empty." }));
  return wrap;
}

function sealedRoom(result) {
  const tables = ((result.staff || {}).spe || {}).tables || {};
  const box = el("div", { class: "sealed" },
    el("div", {}, el("p", { class: "big", text: result.answer.cohort_size.toLocaleString("en-GB") }), el("p", { class: "big-label", text: "patients copied in" })),
    el("div", {},
      el("p", { text: "Only these record types were copied, with pseudonymised patient IDs:" }),
      el("ul", { class: "tables" }, Object.entries(tables).map(([t, c]) => el("li", { text: `${t}: ${c.toLocaleString("en-GB")} rows` }))),
      el("p", { text: "You can analyse the records inside the environment. Only non-personal results, such as model weights or aggregate figures, can leave after staff review." })));
  const status = el("p", { class: "refusal", role: "status", hidden: "" });
  const btn = el("button", { type: "button", class: "dl-btn", text: "Try to download the records" });
  btn.addEventListener("click", async () => {
    const res = await api(`/api/spe/${encodeURIComponent(result.id)}/download`, { method: "POST", body: JSON.stringify({ table: "all records" }) });
    if (res.status === 403) {
      btn.textContent = "Download blocked";
      btn.disabled = true;
      status.replaceChildren(document.createTextNode("Download refused. Personal data may not leave the secure environment (Art. 73)."),
        el("small", { text: `Attempt logged at ${fmtDate(res.body.logged_at)}.` }));
    } else {
      status.textContent = res.body.error || "The download check did not answer.";
    }
    status.hidden = false;
  });
  box.append(el("div", { class: "dl-row" }, btn, status));
  return box;
}

/* staff */
async function loadQueue(selectId) {
  const res = await api("/api/cases");
  const list = $("#queue-list");
  const cases = res.body || [];
  list.replaceChildren();
  if (!cases.length) {
    list.append(el("p", { class: "empty", text: "No cases yet. Submit a request in the applicant view or decide the 10 sample requests." }));
    return;
  }
  const review = cases.filter((c) => c.needs_staff_review && c.status !== "reviewed");
  const rest = cases.filter((c) => !review.includes(c)).sort((a, b) => b.decided_at.localeCompare(a.decided_at) || a.id.localeCompare(b.id));
  list.append(el("h2", { class: "group-title review", text: review.length ? `Needs review (${review.length})` : "No cases need review" }));
  review.forEach((c) => list.append(caseRow(c)));
  list.append(el("h2", { class: "group-title", text: `Decided (${rest.length})` }));
  rest.forEach((c) => list.append(caseRow(c)));
  if (selectId) openCase(selectId);
}

function caseRow(c) {
  const btn = el("button", { type: "button", class: "case-row", "data-id": c.id },
    el("span", { class: "code", text: c.id }),
    el("span", { class: "org", text: c.organisation }),
    el("span", { class: `sub d-${c.decision}` }, el("span", { class: "mark" }), c.decision, c.staff_action ? ` · ${c.staff_action.action}` : ""),
    c.needs_staff_review && c.status !== "reviewed" ? el("span", { class: "why", text: c.review_note || "The two readers of the request disagree." }) : null);
  btn.addEventListener("click", () => openCase(c.id));
  return btn;
}

$("#run-samples").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  btn.disabled = true;
  if (!examples.length) await loadExamples();
  for (const [i, ex] of examples.entries()) {
    btn.textContent = `Deciding ${i + 1} of ${examples.length}...`;
    await api("/api/decide", { method: "POST", body: JSON.stringify(ex) });
  }
  btn.textContent = "Decide the 10 sample requests";
  btn.disabled = false;
  loadQueue();
});

function highlight(text, quote) {
  const p = el("p", { class: "original" });
  const i = quote ? text.toLowerCase().indexOf(quote.toLowerCase()) : -1;
  if (i < 0) { p.textContent = text; return p; }
  p.append(text.slice(0, i), el("mark", { text: text.slice(i, i + quote.length) }), text.slice(i + quote.length));
  return p;
}

function yn(v) { return v === true ? "Yes" : v === false ? "No" : "-"; }

async function openCase(id) {
  document.querySelectorAll(".case-row").forEach((r) => r.setAttribute("aria-current", String(r.dataset.id === id)));
  const res = await api(`/api/cases/${encodeURIComponent(id)}`);
  const cf = $("#casefile");
  if (!res.ok) { cf.replaceChildren(el("p", { class: "empty", text: res.body.error || "Case not found." })); return; }
  const { request, result, audit, staff_action: action } = res.body;
  const staff = result.staff || {};
  const reading = result.reading || {};
  const second = reading.second_opinion;

  const head = el("div", { class: `cf-head d-${result.decision}` },
    el("h2", { class: "code", text: result.id }),
    el("span", { class: "verdict-code" }, el("span", { class: "mark" }), el("span", { class: "code decision-code", text: result.decision })),
    el("span", { text: request.applicant.organisation }));

  const decision = el("section", { class: "cf-section" }, el("h3", { text: "Decision" }),
    el("dl", { class: "facts" },
      el("dt", { text: "Rule applied" }), el("dd", { text: `Step ${result.rule} of 4: ${STEPS[result.rule - 1]}` }),
      el("dt", { text: "Articles" }), el("dd", { class: "code", text: result.articles.map((a) => `Art. ${a}`).join(", ") }),
      el("dt", { text: "Requested as" }), el("dd", { text: request.requested_as }),
      el("dt", { text: "Decided" }), el("dd", { text: fmtDate(res.body.decided_at) })),
    staff.review_note ? el("p", { class: "review-flag", text: staff.review_note }) : null);

  const readerName = result.reader === "keywords" ? "Keyword reader only (no AI key set)" : `AI reader (${result.reader})`;
  const rows = [["Prohibited purpose (Art. 54)", "prohibited"], ["Explains why records are needed", "justifies_records"]];
  const readers = el("section", { class: "cf-section" }, el("h3", { text: "Who read the request" }),
    el("table", { class: "readers" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Question" }), el("th", { scope: "col", text: readerName }), second ? el("th", { scope: "col", text: "Keyword reader (second opinion)" }) : null)),
      el("tbody", {}, rows.map(([q, k]) => {
        const differ = second && second[k] !== reading[k];
        return el("tr", {}, el("th", { scope: "row", text: q }),
          el("td", { class: differ ? "differ" : "", text: yn(reading[k]) }),
          second ? el("td", { class: differ ? "differ" : "", text: yn(second[k]) }) : null);
      }))),
    second ? el("p", { class: `agree ${result.needs_staff_review ? "no" : ""}`, text: result.needs_staff_review ? "The readers disagree on a point that changes the outcome." : "The readers agree where it matters." }) : null);

  const original = el("section", { class: "cf-section" }, el("h3", { text: "The request as submitted" }),
    el("p", { class: "hint", text: "Purpose" }), highlight(request.purpose, result.evidence),
    el("p", { class: "hint", text: "Question" }), highlight(request.question, result.evidence),
    el("p", { class: "hint", text: "Definitions" }), el("ul", { class: "mapping" }, (request.definitions || []).map((d) => el("li", { text: d }))));

  const plan = staff.plan || staff.spec;
  const query = el("section", { class: "cf-section" }, el("h3", { text: "How the numbers were computed" }));
  if (plan) {
    query.append(el("p", { text: staff.planner === "rules" ? "Planned by the rule planner from the definitions." : `Planned by the AI planner (${staff.planner}) and checked against the rule planner.` }));
    query.append(el("details", { class: "sql" }, el("summary", { text: "Query plan" }), el("pre", { text: JSON.stringify(plan, null, 2) })));
    const sql = staff.sql || (staff.spe || {}).cohort_sql;
    if (sql) query.append(el("details", { class: "sql" }, el("summary", { text: "Generated SQL" }), el("pre", { text: sql })));
  } else {
    query.append(el("p", { text: "Nothing was computed: the request was refused." }));
  }

  const sections = [head, decision, readers, original, query];
  if (staff.spe) {
    sections.push(el("section", { class: "cf-section" }, el("h3", { text: "Secure processing environment" }),
      el("dl", { class: "facts" },
        el("dt", { text: "Workspace" }), el("dd", { class: "code", text: staff.spe.workspace }),
        el("dt", { text: "Patients" }), el("dd", { text: staff.spe.cohort_size.toLocaleString("en-GB") }),
        el("dt", { text: "Tables" }), el("dd", { text: Object.entries(staff.spe.tables).map(([t, c]) => `${t} (${c.toLocaleString("en-GB")})`).join(", ") }),
        el("dt", { text: "Downloads" }), el("dd", { text: staff.spe.downloads })),
      el("h3", { text: "Download attempts" }),
      audit.length ? el("ul", { class: "mapping" }, audit.map((a) => el("li", { text: `${fmtDate(a.at)}: ${a.table}, ${a.result}` }))) : el("p", { class: "hint", text: "None so far." })));
  }

  const actions = el("section", { class: "cf-section" }, el("h3", { text: "Your action" }));
  if (action) {
    actions.append(el("p", { class: "staff-done", text: action.action === "confirmed" ? `Confirmed ${fmtDate(action.at)}.` : `Overruled to ${action.decision} ${fmtDate(action.at)}: ${action.reason}` }));
  } else {
    const panel = el("form", { class: "overrule", hidden: "" },
      el("fieldset", { class: "kind" }, el("legend", { text: "Change the decision to" }),
        ["REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE"].filter((d) => d !== result.decision).map((d, i) =>
          el("label", { class: "choice" }, el("input", { type: "radio", name: "decision", value: d, checked: i === 0 ? "" : false }), el("span", { class: "code", text: d })))),
      el("label", {}, "Reason (shown to the applicant)", el("textarea", { name: "reason", rows: "3", required: "" })),
      el("p", { class: "form-error", role: "alert", hidden: "" }),
      el("button", { type: "submit", class: "primary", text: "Overrule decision" }));
    panel.addEventListener("submit", async (e) => {
      e.preventDefault();
      const r = await api(`/api/cases/${encodeURIComponent(id)}/overrule`, { method: "POST", body: JSON.stringify({ decision: panel.decision.value, reason: panel.reason.value }) });
      if (!r.ok) { const er = $(".form-error", panel); er.textContent = r.body.error; er.hidden = false; return; }
      loadQueue(id);
    });
    const confirm = el("button", { type: "button", class: "primary", text: "Confirm decision" });
    confirm.addEventListener("click", async () => { await api(`/api/cases/${encodeURIComponent(id)}/confirm`, { method: "POST", body: "{}" }); loadQueue(id); });
    const toggle = el("button", { type: "button", class: "quiet", "aria-expanded": "false", text: "Overrule" });
    toggle.addEventListener("click", () => { panel.hidden = !panel.hidden; toggle.setAttribute("aria-expanded", String(!panel.hidden)); });
    actions.append(el("div", { class: "actions" }, confirm, toggle), panel);
  }
  sections.push(actions);
  cf.replaceChildren(...sections);
}

loadExamples();
