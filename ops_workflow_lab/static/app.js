"use strict";
const $ = (id) => document.getElementById(id);
let current = null;
let source = null;
let events = new Map();
let refreshTimer;
let noticeTimer;
let selection = 0;
let plannerMode = "deterministic";
const terminalStates = [
  "succeeded",
  "failed",
  "rejected",
  "partial_failure",
  "cancelled",
];
let recentRuns = [];
let runFilter = "all";

function showTable() {
  const search = $("run-search").value.toLowerCase();
  const filtered = recentRuns.filter(
    (run) =>
      `${run.goal} ${run.id}`.toLowerCase().includes(search) &&
      (runFilter === "all" ||
        run.status === runFilter ||
        (runFilter === "attention" &&
          ["failed", "partial_failure"].includes(run.status))),
  );
  $("run-rows").replaceChildren(
    ...filtered.map((run) => {
      const row = element("tr");
      const name = element("td");
      const open = element("button", "", run.goal);
      open.addEventListener("click", async () => {
        try {
          await selectRun(run.id);
          $("run-detail").scrollIntoView({ block: "start" });
        } catch (error) {
          notice(error.message);
        }
      });
      name.append(open, element("small", "", run.id.slice(0, 12)));
      const status = element("td");
      status.append(
        element("span", `badge ${run.status}`, run.status.replaceAll("_", " ")),
      );
      row.append(
        name,
        status,
        element("td", "", run.plan?.target || "—"),
        element(
          "td",
          "",
          new Date(run.created_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
        ),
      );
      return row;
    }),
  );
  $("run-table-caption").textContent =
    `${filtered.length} of ${recentRuns.length} recent workflows${filtered.length ? " · Select a workflow to inspect its trace." : " · No matching workflows."}`;
}

function showEvidence(run) {
  const policies = run.plan.policies || [];
  $("evidence-count").textContent = new Set(
    policies.flatMap((p) => p.evidence.map((d) => d.id)),
  ).size;
  $("evidence").replaceChildren(
    ...policies.map((policy) => {
      const card = element("section", "policy-card");
      card.append(
        element("h3", "", policy.target),
        element(
          "p",
          "",
          `Validated controls · ${policy.attempts} generation attempt(s) · synthetic runbooks`,
        ),
      );
      const controls = element("ul", "control-list");
      policy.controls.forEach((item) => {
        const row = element("li");
        const link = element("a", "", item.source_id);
        const sourceId = `source-${policy.target}-${item.source_id}`;
        link.href = `#${sourceId}`;
        link.addEventListener("click", () => {
          const source = $(sourceId);
          if (source) source.open = true;
        });
        row.append(
          element("span", "", item.control.replaceAll("_", " ")),
          link,
        );
        controls.append(row);
      });
      card.append(controls);
      policy.evidence.forEach((doc) => {
        const details = element("details", "evidence-source");
        details.id = `source-${policy.target}-${doc.id}`;
        details.append(
          element("summary", "", doc.title),
          element("p", "", doc.text),
          element(
            "small",
            "",
            `${doc.id} · cosine ${doc.score.toFixed(3)} · sha256 ${doc.content_hash.slice(0, 12)}`,
          ),
        );
        card.append(details);
      });
      const trace = element("details", "evidence-source");
      trace.append(
        element("summary", "", "Planning graph trace"),
        element("pre", "", JSON.stringify(policy.trace, null, 2)),
      );
      card.append(trace);
      return card;
    }),
  );
  if (!policies.length)
    $("evidence").append(
      element(
        "p",
        "form-note",
        "This plan uses no retrieved evidence. Start the server in RAG mode to inspect grounded policies.",
      ),
    );
  $("target-outcomes").replaceChildren(
    ...(run.plan.targets || [run.plan.target]).map((target) => {
      const steps = run.steps.filter(
        (s) =>
          (run.plan.steps[s.position].target || run.plan.target) === target &&
          s.tool !== "join",
      );
      const status = steps.some((s) => s.status === "failed")
        ? "failed"
        : steps.every((s) => s.status === "succeeded")
          ? "succeeded"
          : terminalStates.includes(run.status)
            ? run.status
            : "pending";
      return element(
        "span",
        status,
        `${target} · ${status.replaceAll("_", " ")}`,
      );
    }),
  );
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    $("notice").hidden = true;
  }, 8000);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Please check the request fields.",
    );
  return body;
}

function showRun(run) {
  current = run;
  $("empty-state").hidden = true;
  $("run-detail").hidden = false;
  $("run-status").className = `badge ${run.status}`;
  $("run-status").textContent = run.status.replaceAll("_", " ");
  $("run-target").textContent = run.plan.target;
  $("run-id").textContent = run.id.slice(0, 12);
  $("run-id").title = run.id;
  const interpretation = run.plan.interpretation;
  $("run-model").hidden = !interpretation;
  $("run-model").textContent = interpretation
    ? `Interpreted by ${interpretation.model} · ${interpretation.latency_ms} ms · ${interpretation.prompt_version}`
    : "";
  $("run-scenario").textContent =
    `Planned scenario: ${{ none: "successful execution", transient: "timeout once, then recover", persistent: "exhaust the retry budget", verification: "fail the integrity check" }[run.plan.failure]}${run.plan.failure_target && run.plan.failure !== "none" ? ` · injected into ${run.plan.failure_target} only` : ""}`;
  $("steps").replaceChildren(
    ...run.steps.map((step) => {
      const node = element("li", `step ${step.status}`);
      node.append(
        element(
          "span",
          "step-number",
          step.status === "succeeded"
            ? "✓"
            : String(step.position + 1).padStart(2, "0"),
        ),
      );
      const copy = element("div", "step-copy");
      copy.append(
        element("div", "step-title", step.title),
        element(
          "div",
          "step-note",
          `${step.tool} · attempts ${step.attempts}${run.plan.steps[step.position].depends_on?.length ? ` · after ${run.plan.steps[step.position].depends_on.join(", ")}` : ""}`,
        ),
      );
      node.append(copy, element("span", "step-status", step.status));
      return node;
    }),
  );
  $("approval").hidden = run.status !== "awaiting_approval";
  const terminal = terminalStates.includes(run.status);
  $("cancel").hidden = terminal || run.status === "awaiting_approval";
  $("outcome").hidden = !terminal;
  $("outcome").className = `outcome ${run.status}`;
  $("outcome").textContent =
    {
      succeeded:
        "✓ Completed. All simulated checks passed; the result is recorded below.",
      failed:
        "Execution stopped. Inspect the trace for the failed check or retry limit.",
      rejected: "Plan rejected. No tools were executed.",
      partial_failure:
        "One or more targets failed. Successful target results are preserved; inspect the final join and trace.",
      cancelled:
        "Remaining work cancelled. Completed simulated operations are preserved.",
    }[run.status] || "";
  $("result-json").textContent = JSON.stringify(run, null, 2);
  showEvidence(run);
}

function showEvents() {
  const sorted = [...events.values()].sort((a, b) => a.seq - b.seq);
  $("event-count").textContent = `${sorted.length} EVENTS`;
  $("trace").replaceChildren(
    ...sorted.map((event) => {
      const node = element("div", `event ${event.kind}`);
      node.append(
        element(
          "time",
          "",
          new Date(event.created_at).toLocaleTimeString("en-GB"),
        ),
        element("span", "event-kind", event.kind.replaceAll("_", " ")),
        element(
          "span",
          "event-message",
          `${event.payload.message || event.kind}${event.payload.attempt ? ` · attempt ${event.payload.attempt}` : ""}`,
        ),
      );
      return node;
    }),
  );
  $("trace").scrollTop = $("trace").scrollHeight;
}

async function history() {
  const runs = await api("/api/runs");
  recentRuns = runs;
  $("metric-total").textContent = $("nav-total").textContent = runs.length;
  $("metric-pending").textContent = runs.filter(
    (r) => r.status === "awaiting_approval",
  ).length;
  $("metric-success").textContent = runs.filter(
    (r) => r.status === "succeeded",
  ).length;
  $("metric-failed").textContent = runs.filter((r) =>
    ["failed", "partial_failure"].includes(r.status),
  ).length;
  showTable();
  $("history").replaceChildren(
    ...runs.slice(0, 8).map((run) => {
      const button = element("button", current?.id === run.id ? "active" : "");
      button.append(
        element("strong", "", run.goal),
        element("small", "", run.status.replaceAll("_", " ")),
      );
      button.addEventListener("click", () =>
        selectRun(run.id).catch((e) => notice(e.message)),
      );
      return button;
    }),
  );
  if (!runs.length)
    $("history").append(element("p", "quiet", "Your runs will appear here."));
  return runs;
}

async function selectRun(id) {
  const generation = ++selection;
  if (source) source.close();
  clearTimeout(refreshTimer);
  const [run, trace] = await Promise.all([
    api(`/api/runs/${id}`),
    api(`/api/runs/${id}/events`),
  ]);
  if (generation !== selection) return;
  events = new Map(trace.map((event) => [event.seq, event]));
  $("goal").value = run.goal;
  $("failure").value = run.plan.failure;
  showRun(run);
  showEvents();
  await history();
  if (generation !== selection) return;
  if (terminalStates.includes(run.status)) return;
  const last = Math.max(0, ...events.keys());
  const stream = new EventSource(`/api/runs/${id}/stream?after=${last}`);
  source = stream;
  stream.addEventListener("trace", (message) => {
    if (generation !== selection) return;
    const event = JSON.parse(message.data);
    events.set(event.seq, event);
    showEvents();
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      try {
        const latest = await api(`/api/runs/${id}`);
        if (
          generation === selection &&
          !terminalStates.includes(current?.status)
        )
          showRun(latest);
      } catch (error) {
        notice(error.message);
      }
    }, 80);
  });
  stream.addEventListener("done", (message) => {
    stream.close();
    if (generation !== selection) return;
    clearTimeout(refreshTimer);
    showRun(JSON.parse(message.data));
    history().catch((e) => notice(e.message));
  });
}

$("request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("create").disabled = true;
  const buttonLabel = $("create").textContent;
  $("create").textContent =
    plannerMode === "rag"
      ? "Retrieving evidence & validating policies…"
      : plannerMode === "ollama"
        ? "Interpreting with local model…"
        : "Building plan…";
  try {
    const run = await api("/api/runs", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        goal: $("goal").value,
        failure: $("failure").value,
      }),
    });
    await selectRun(run.id);
  } catch (error) {
    notice(error.message);
  } finally {
    $("create").disabled = false;
    $("create").textContent = buttonLabel;
  }
});

for (const decision of ["approve", "reject", "cancel"]) {
  $(decision).addEventListener("click", async () => {
    if (!current) return;
    const runId = current.id;
    const generation = selection;
    $("approve").disabled = $("reject").disabled = $("cancel").disabled = true;
    try {
      const run = await api(`/api/runs/${runId}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, plan_hash: current.plan.hash }),
      });
      if (generation === selection) showRun(run);
      await history();
    } catch (error) {
      notice(error.message);
    } finally {
      $("approve").disabled =
        $("reject").disabled =
        $("cancel").disabled =
          false;
    }
  });
}

document.querySelectorAll("[data-goal]").forEach((button) => {
  button.addEventListener("click", () => {
    $("goal").value = button.dataset.goal;
    if (button.dataset.goal === "Show inventory") $("failure").value = "none";
    $("goal").focus();
  });
});
$("refresh").addEventListener("click", () =>
  history().catch((e) => notice(e.message)),
);

async function init() {
  const health = await api("/api/health");
  plannerMode = health.planner;
  if (plannerMode !== "deterministic") {
    $("planner-label").textContent = "Local LLM planner";
    $("planner-description").textContent = health.model;
    $("planner-tag").textContent = "OLLAMA";
    $("planner-help").textContent =
      "Describe one operation in Korean or English and name a fictional target. The local model proposes; you review and approve.";
  }
  if (plannerMode === "rag") {
    $("planner-label").textContent = "Grounded planning graph";
    $("planner-description").textContent =
      `${health.model} + ${health.embedding_model}`;
    $("planner-tag").textContent = "RAG + DAG";
    $("planner-help").textContent =
      "Name up to three fictional targets for one operation. Review retrieved evidence and validated controls, then approve the complete plan once. Failure scenarios affect the first target only.";
    $("batch-preset").hidden = false;
  }
  const targets = await api("/api/targets");
  $("targets").replaceChildren(
    ...targets.map((target) => {
      const row = element("div", "target");
      const description = element("div");
      description.append(
        element("strong", "", target.id),
        element("small", "", `${target.role} · ${target.region}`),
      );
      row.append(
        element("span", "target-icon", "▤"),
        description,
        element("span", "healthy", "● HEALTHY"),
      );
      return row;
    }),
  );
  const runs = await history();
  if (runs.length) await selectRun(runs[0].id);
}
$("run-search").addEventListener("input", showTable);
document.querySelectorAll("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    runFilter = button.dataset.filter;
    document
      .querySelectorAll("[data-filter]")
      .forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)),
      );
    showTable();
  }),
);
const tabs = [...document.querySelectorAll("[data-view]")];
tabs.forEach((button, index) => {
  button.addEventListener("click", () =>
    tabs.forEach((tab) => {
      const selected = tab === button;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      $(`view-${tab.dataset.view}`).hidden = !selected;
    }),
  );
  button.addEventListener("keydown", (event) => {
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index + tabs.length - 1) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabs.length - 1
              : null;
    if (next !== null) {
      event.preventDefault();
      tabs[next].click();
      tabs[next].focus();
    }
  });
});
try {
  document.documentElement.dataset.theme =
    localStorage.getItem("ops-theme") || "light";
} catch {
  /* Storage is optional. */
}
$("theme").addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("ops-theme", theme);
  } catch {
    /* Storage is optional. */
  }
});
init().catch((error) => notice(error.message));
