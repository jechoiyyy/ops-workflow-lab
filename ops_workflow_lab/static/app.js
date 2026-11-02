"use strict";
const $ = (id) => document.getElementById(id);
let current = null;
let source = null;
let events = new Map();
let refreshTimer;
let noticeTimer;
let selection = 0;

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
  $("run-scenario").textContent =
    `Planned scenario: ${{ none: "successful execution", transient: "timeout once, then recover", persistent: "exhaust the retry budget", verification: "fail the integrity check" }[run.plan.failure]}`;
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
          `${step.tool} · ${run.plan.steps[step.position].effect.replaceAll("_", " ")} · attempts ${step.attempts}`,
        ),
      );
      node.append(copy, element("span", "step-status", step.status));
      return node;
    }),
  );
  $("approval").hidden = run.status !== "awaiting_approval";
  const terminal = ["succeeded", "failed", "rejected"].includes(run.status);
  $("outcome").hidden = !terminal;
  $("outcome").className = `outcome ${run.status}`;
  $("outcome").textContent =
    {
      succeeded:
        "✓ Completed. All simulated checks passed; the result is recorded below.",
      failed:
        "Execution stopped. Inspect the trace for the failed check or retry limit.",
      rejected: "Plan rejected. No tools were executed.",
    }[run.status] || "";
  $("result-json").textContent = JSON.stringify(run, null, 2);
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
  $("history").replaceChildren(
    ...runs.map((run) => {
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
  showRun(run);
  showEvents();
  await history();
  if (generation !== selection) return;
  if (["succeeded", "failed", "rejected"].includes(run.status)) return;
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
          !["succeeded", "failed", "rejected"].includes(current?.status)
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
  }
});

for (const decision of ["approve", "reject"]) {
  $(decision).addEventListener("click", async () => {
    if (!current) return;
    const runId = current.id;
    const generation = selection;
    $("approve").disabled = $("reject").disabled = true;
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
      $("approve").disabled = $("reject").disabled = false;
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
init().catch((error) => notice(error.message));
