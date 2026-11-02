"use strict";
const $ = (id) => document.getElementById(id);
const terminalStates = [
  "succeeded",
  "failed",
  "rejected",
  "partial_failure",
  "cancelled",
];
const statuses = {
  succeeded: "성공",
  failed: "실패",
  rejected: "거절",
  partial_failure: "부분 실패",
  cancelled: "취소",
  pending: "대기",
  retrying: "재시도",
  running: "실행 중",
  queued: "실행 대기",
  awaiting_approval: "승인 대기",
  skipped: "건너뜀",
  idle: "준비",
};
const tools = {
  inventory: "서버 목록 조회",
  inspect: "대상 상태 확인",
  apply_policy: "정책 제어 항목 적용",
  snapshot: "모의 스냅샷 생성",
  sandbox: "가상 복구 환경 생성",
  verify: "실행 결과 검증",
  join: "대상별 결과 합산",
};
const controls = {
  preserve_source: "원본 유지",
  checksum: "체크섬 검증",
  application_checkpoint: "애플리케이션 체크포인트",
  pause_writes: "쓰기 일시 중지",
  resume_writes: "쓰기 재개",
  queue_checkpoint: "작업 큐 체크포인트",
  isolate_sandbox: "복구 환경 격리",
  readiness_check: "준비 상태 확인",
  read_only_queries: "읽기 전용 검증 쿼리",
  read_only: "읽기 전용",
};
const sourceCopy = {
  "backup-core": [
    "모의 백업 무결성",
    "가상 원본을 유지하고 생성된 모의 스냅샷의 체크섬을 검증합니다.",
  ],
  "backup-application": [
    "애플리케이션 스냅샷 일관성",
    "스냅샷을 생성하기 전에 모의 애플리케이션 체크포인트를 기록합니다.",
  ],
  "backup-database": [
    "데이터베이스 쓰기 일관성",
    "스냅샷 생성 전에 가상의 쓰기를 일시 중지하고, 이후 쓰기를 재개합니다.",
  ],
  "backup-worker": [
    "작업자 처리 위치 보존",
    "완료되지 않은 작업의 가상 큐 처리 위치를 기록합니다.",
  ],
  "rehearsal-core": [
    "격리된 복구 리허설",
    "격리된 가상 환경에서 복구를 연습하고, 원본을 유지하며 준비 상태를 확인합니다.",
  ],
  "rehearsal-database": [
    "읽기 전용 데이터베이스 리허설",
    "읽기 전용 테스트 쿼리로 모의 복구 환경을 확인합니다.",
  ],
  "inventory-core": [
    "가상 서버 목록 조회",
    "서버 목록을 조회하며 대상을 변경하지 않습니다.",
  ],
};
const icons = {
  overview:
    '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  workflow:
    '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M6 9v9h9M9 6h9v9"/>',
  runs: '<path d="M9 5h12M9 12h12M9 19h12M3 5h1M3 12h1M3 19h1"/>',
  sparkles:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4"/>',
  trace: '<path d="M5 3v16h16M5 7h6m-6 6h12M11 5v4m6 2v4m4 2v4"/>',
  database:
    '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  book: '<path d="M12 5v15M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2Z"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1 1m12 12 1 1M5 19l1-1M18 6l1-1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
  refresh:
    '<path d="M20 7a9 9 0 0 0-15-2L3 7m0-5v5h5M4 17a9 9 0 0 0 15 2l2-2m0 5v-5h-5"/>',
  shield:
    '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  warning: '<path d="m12 3 10 18H2ZM12 9v4m0 4h.01"/>',
  server:
    '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h.01M7 17h.01M11 6h6m-6 11h6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  search: '<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
};
function icon(name) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  node.setAttribute("viewBox", "0 0 24 24");
  node.setAttribute("fill", "none");
  node.setAttribute("stroke", "currentColor");
  node.setAttribute("stroke-width", "1.6");
  node.setAttribute("stroke-linecap", "round");
  node.setAttribute("stroke-linejoin", "round");
  node.setAttribute("aria-hidden", "true");
  node.innerHTML = icons[name] || icons.workflow;
  return node;
}
document
  .querySelectorAll("[data-icon]")
  .forEach((n) => n.replaceWith(icon(n.dataset.icon)));
let current = null,
  source = null,
  events = new Map(),
  selection = 0,
  refreshTimer,
  noticeTimer;
let recentRuns = [],
  runFilter = "all",
  plannerMode = "deterministic",
  selectedStep = 0,
  page = "overview",
  evidenceHash = null;
const statusLabel = (value) => statuses[value] || "확인 필요";
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function notice(message) {
  (document.querySelector("dialog[open]") || document.body).append($("notice"));
  $("notice").textContent = message;
  $("notice").hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => ($("notice").hidden = true), 8000);
}
function apiError(status, detail) {
  const reason = typeof detail === "string" ? detail : "";
  if (/busy|already processing/i.test(reason))
    return "다른 계획을 생성 중입니다. 잠시 후 다시 시도하세요.";
  if (/two attempts|Policy validation/.test(reason))
    return "두 번의 정책 생성에서 검증을 통과하지 못했습니다. 실행 계획은 생성되지 않았습니다.";
  if (/evidence is missing/.test(reason))
    return "필수 근거 문서가 부족하여 계획 생성을 중단했습니다.";
  if (
    /target|operation|supported|grammar|command|interpret|request/i.test(
      reason,
    ) &&
    status === 400
  )
    return "요청을 해석할 수 없습니다. 지원하는 작업 하나와 가상 대상 이름을 명확히 입력하세요. 예시 버튼도 사용할 수 있습니다.";
  if (/inventory|Failure injection/i.test(reason))
    return "목록 조회에는 ‘정상 실행’ 시나리오를 선택하세요.";
  return (
    {
      400: "요청 내용을 확인하세요. 예시 명령과 지원하는 시나리오를 사용할 수 있습니다.",
      403: "허용되지 않은 요청입니다. 로컬 데모 주소에서 다시 시도하세요.",
      404: "실행 기록을 찾을 수 없습니다. 목록을 새로고침하세요.",
      409: "실행 상태 또는 계획이 변경되었습니다. 상세 화면을 다시 열어 확인하세요.",
      422: "입력 항목이 올바르지 않습니다. 요청은 1~180자로 입력하세요.",
      503: "로컬 모델의 응답을 확인할 수 없습니다. Ollama 실행 상태와 설치된 모델 이름을 확인한 뒤 다시 시도하세요.",
    }[status] || "요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하세요."
  );
}
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "로컬 서버에 연결할 수 없습니다. 서버 실행 상태를 확인하세요.",
    );
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error("서버 응답을 읽을 수 없습니다. 페이지를 새로고침하세요.");
  }
  if (!response.ok) throw new Error(apiError(response.status, body.detail));
  return body;
}
function openDialog(id) {
  const dialog = $(id);
  if (!dialog.open) dialog.showModal();
}
function setPage(next) {
  page = next;
  const title = {
    overview: "운영 개요",
    runs: "실행 탐색",
    sources: "데이터 소스",
  }[next];
  $("page-title").textContent = $("breadcrumb").textContent = title;
  $("overview-panel").hidden = next !== "overview";
  $("runs-panel").hidden = next === "sources";
  $("sources-panel").hidden = next !== "sources";
  document
    .querySelectorAll("nav [data-page]")
    .forEach((n) => n.classList.toggle("nav-current", n.dataset.page === next));
  document.body.classList.remove("mobile-nav");
  window.scrollTo({ top: 0 });
}
function setFilter(next) {
  runFilter = next;
  document
    .querySelectorAll("[data-filter]")
    .forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.filter === next)),
    );
  showTable();
}
function showTable() {
  const query = $("run-search").value.toLowerCase();
  const filtered = recentRuns.filter(
    (r) =>
      `${r.goal} ${r.id} ${r.plan.target}`.toLowerCase().includes(query) &&
      (runFilter === "all" ||
        r.status === runFilter ||
        (runFilter === "attention" &&
          ["failed", "partial_failure"].includes(r.status))),
  );
  $("run-rows").replaceChildren(
    ...filtered.map((run) => {
      const row = element("tr");
      const name = element("td");
      const button = element("button", "run-name");
      button.append(
        element("strong", "", run.goal),
        element("small", "mono", run.id.slice(0, 12)),
      );
      button.addEventListener("click", () =>
        selectRun(run.id).catch((e) => notice(e.message)),
      );
      name.append(button);
      const status = element("td");
      status.append(
        element("span", `badge ${run.status}`, statusLabel(run.status)),
      );
      const target = element("td", "target-cell");
      target.append(icon("server"), element("span", "", run.plan.target));
      const open = element("button", "icon-button");
      open.setAttribute("aria-label", `${run.goal} 상세 보기`);
      open.append(icon("chevron"));
      open.addEventListener("click", () =>
        selectRun(run.id).catch((e) => notice(e.message)),
      );
      const end = element("td");
      end.append(open);
      row.append(
        name,
        status,
        target,
        element(
          "td",
          "date-cell",
          new Date(run.created_at).toLocaleString("ko-KR", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          }),
        ),
        end,
      );
      return row;
    }),
  );
  if (!filtered.length) {
    const row = element("tr");
    const cell = element(
      "td",
      "table-empty",
      query || runFilter !== "all"
        ? "조건에 맞는 실행이 없습니다."
        : "아직 실행 기록이 없습니다. 새 워크플로를 만들어 보세요.",
    );
    cell.colSpan = 5;
    row.append(cell);
    $("run-rows").append(row);
  }
  $("run-table-caption").textContent =
    `최근 ${recentRuns.length}건 중 ${filtered.length}건 표시 · 워크플로를 선택하면 실행 상세가 열립니다.`;
  $("run-total-label").textContent = `${recentRuns.length}건`;
}
function svgNode(tag, attrs, text) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  if (text !== undefined) n.textContent = text;
  return n;
}
function showAnalytics() {
  const now = Date.now(),
    start = now - 24 * 3600000,
    buckets = Array.from({ length: 12 }, () => [0, 0, 0]);
  let total = 0;
  for (const run of recentRuns) {
    const time = Date.parse(run.created_at);
    if (time < start || time > now) continue;
    const index = Math.min(11, Math.floor((time - start) / 7200000));
    buckets[index][
      run.status === "succeeded"
        ? 0
        : ["failed", "partial_failure"].includes(run.status)
          ? 1
          : 2
    ]++;
    total++;
  }
  const svg = svgNode("svg", {
      viewBox: "0 0 640 230",
      preserveAspectRatio: "none",
    }),
    max = Math.max(
      3,
      Math.ceil(
        Math.max(...buckets.map((b) => b.reduce((a, v) => a + v, 0))) / 3,
      ) * 3,
    ),
    colors = ["var(--accent)", "var(--danger)", "var(--chart-gray)"];
  const defs = svgNode("defs", {});
  colors.forEach((color, i) => {
    const p = svgNode("pattern", {
      id: `dots-${i}`,
      width: 7,
      height: 7,
      patternUnits: "userSpaceOnUse",
    });
    p.append(
      svgNode("circle", { cx: 3, cy: 3, r: 1, fill: color, opacity: 0.5 }),
    );
    defs.append(p);
  });
  svg.append(defs);
  for (let i = 0; i < 4; i++) {
    const y = 18 + i * 56;
    svg.append(
      svgNode("line", { x1: 35, y1: y, x2: 622, y2: y, class: "grid-line" }),
      svgNode(
        "text",
        { x: 25, y: y + 4, "text-anchor": "end", class: "axis-label" },
        String(Math.round((max * (3 - i)) / 3)),
      ),
    );
  }
  colors.forEach((color, series) => {
    if (!buckets.some((b) => b[series])) return;
    const points = buckets.map((b, i) => [
      35 + i * (587 / 11),
      186 - (b.slice(0, series + 1).reduce((a, v) => a + v, 0) / max) * 168,
    ]);
    const lower = buckets
      .map((b, i) => [
        35 + i * (587 / 11),
        186 - (b.slice(0, series).reduce((a, v) => a + v, 0) / max) * 168,
      ])
      .reverse()
      .map((p) => `L${p[0]},${p[1]}`)
      .join(" ");
    const path = points
      .map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`)
      .join(" ");
    svg.append(
      svgNode("path", {
        d: `${path} ${lower} Z`,
        fill: `url(#dots-${series})`,
      }),
      svgNode("path", {
        d: path,
        fill: "none",
        stroke: color,
        "stroke-width": 1.5,
      }),
    );
  });
  [0, 3, 6, 9, 11].forEach((i) =>
    svg.append(
      svgNode(
        "text",
        {
          x: 35 + i * (587 / 11),
          y: 220,
          "text-anchor": i === 0 ? "start" : i === 11 ? "end" : "middle",
          class: "axis-label",
        },
        new Date(start + (i + 1) * 7200000).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
      ),
    ),
  );
  $("trend-chart").replaceChildren(svg);
  $("trend-chart").setAttribute(
    "aria-label",
    `최근 30건 가운데 지난 24시간에 생성된 실행 ${total}건. 현재 상태별 추이이며 시간별 성능 지표가 아닙니다.`,
  );
  $("trend-caption").textContent = `24시간 내 ${total}건 · 현지 시각`;
  const counts = ["atlas-api", "lumen-db", "cedar-worker"].map((target) => ({
      target,
      count: recentRuns.filter((r) =>
        (r.plan.targets || [r.plan.target]).includes(target),
      ).length,
    })),
    highest = Math.max(1, ...counts.map((c) => c.count));
  $("target-activity").replaceChildren(
    ...counts.map(({ target, count }) => {
      const button = element("button", "activity-row");
      const heading = element("span", "activity-heading");
      const avatar = element("span", "agent-avatar");
      avatar.append(icon("server"));
      heading.append(
        avatar,
        element("span", "", target),
        element("strong", "", `${count}건`),
      );
      const meter = element("progress");
      meter.max = highest;
      meter.value = count;
      meter.setAttribute("aria-label", `${target} 참여 ${count}건`);
      button.append(heading, meter);
      button.addEventListener("click", () => {
        setPage("runs");
        $("run-search").value = target;
        setFilter("all");
      });
      return button;
    }),
  );
  const failed = recentRuns.filter((r) =>
    ["failed", "partial_failure"].includes(r.status),
  ).length;
  $("attention-banner").hidden = !failed;
  $("attention-title").textContent = `확인이 필요한 실행 ${failed}건`;
}
function stepName(run, step) {
  const spec = run.plan.steps[step.position];
  return `${spec.target && spec.target !== "all" ? `${spec.target} · ` : ""}${tools[step.tool] || "실행 단계"}`;
}
function showStep() {
  if (!current) return;
  const step = current.steps[selectedStep] || current.steps[0];
  if (!step) return;
  const spec = current.plan.steps[step.position];
  const root = $("step-detail");
  root.replaceChildren();
  const heading = element("div", "step-heading");
  const avatar = element("span", "code-icon");
  avatar.append(icon(step.tool === "join" ? "workflow" : "server"));
  const title = element("div");
  title.append(
    element("h3", "", tools[step.tool] || "실행 단계"),
    element("small", "mono", spec.id || `step-${step.position + 1}`),
  );
  heading.append(
    avatar,
    title,
    element("span", `badge ${step.status}`, statusLabel(step.status)),
  );
  const info = element("dl", "info-list");
  for (const [label, value] of [
    ["대상", spec.target || current.plan.target],
    ["시도 횟수", `${step.attempts}회`],
    ["선행 단계", spec.depends_on?.join(", ") || "없음"],
    [
      "작업 종류",
      spec.effect === "simulated_write" ? "모의 변경" : "읽기 전용",
    ],
  ])
    info.append(element("dt", "", label), element("dd", "", value));
  root.append(heading, info, element("h4", "io-label", "실행 결과"));
  if (step.result)
    root.append(element("pre", "", JSON.stringify(step.result, null, 2)));
  else
    root.append(
      element(
        "div",
        "io-empty",
        step.status === "failed"
          ? "실행에 실패했습니다. 이벤트 탭에서 원인을 확인하세요."
          : step.status === "skipped"
            ? "이 단계는 실행되지 않았습니다."
            : "아직 실행 결과가 없습니다. 승인과 선행 단계가 완료되면 실행됩니다.",
      ),
    );
  document.querySelectorAll(".step-node").forEach((n, i) => {
    n.classList.toggle("active", i === selectedStep);
    n.setAttribute("aria-pressed", String(i === selectedStep));
  });
}
function showEvidence(run) {
  const policies = run.plan.policies || [];
  $("evidence-count").textContent = new Set(
    policies.flatMap((p) => p.evidence.map((d) => d.id)),
  ).size;
  if (evidenceHash !== run.plan.hash) {
    evidenceHash = run.plan.hash;
    $("evidence").replaceChildren(
      ...policies.map((policy) => {
        const card = element("section", "policy-card");
        card.append(
          element("h3", "", policy.target),
          element(
            "p",
            "muted",
            `제어 항목 검증 완료 · 생성 ${policy.attempts}회 · 합성 런북`,
          ),
        );
        const list = element("ul", "control-list");
        for (const item of policy.controls) {
          const row = element("li");
          const link = element(
            "button",
            "source-link",
            sourceCopy[item.source_id]?.[0] || item.source_id,
          );
          const id = `source-${policy.target}-${item.source_id}`;
          link.addEventListener("click", () => {
            const doc = $(id);
            doc.open = true;
            doc.scrollIntoView({ block: "nearest" });
          });
          row.append(
            element("span", "", controls[item.control] || item.control),
            link,
          );
          list.append(row);
        }
        card.append(list);
        for (const doc of policy.evidence) {
          const detail = element("details", "evidence-source");
          detail.id = `source-${policy.target}-${doc.id}`;
          const translation = sourceCopy[doc.id];
          detail.append(
            element("summary", "", translation?.[0] || doc.title),
            element("p", "", translation?.[1] || doc.text),
            element(
              "small",
              "mono",
              `${doc.id} · 코사인 유사도 ${doc.score.toFixed(3)}`,
            ),
          );
          const original = element("details", "source-original");
          original.append(
            element("summary", "", "저장된 원문 보기"),
            element("p", "", doc.text),
            element("small", "mono", `SHA-256 ${doc.content_hash}`),
          );
          detail.append(original);
          card.append(detail);
        }
        const trace = element("details", "evidence-source");
        trace.append(element("summary", "", "계획 생성 과정"));
        for (const node of policy.trace) {
          const label =
            {
              retrieve: "근거 문서 검색",
              generate_policy: "정책 생성",
              validate_policy: "정책 검증",
            }[node.node] || "계획 단계";
          trace.append(
            element(
              "p",
              "",
              `${label}${node.attempt ? ` · ${node.attempt}회차` : ""}${node.accepted !== undefined ? ` · ${node.accepted ? "통과" : "재검토 필요"}` : ""}${node.source_ids ? ` · ${node.source_ids.join(", ")}` : ""}`,
            ),
          );
        }
        card.append(trace);
        return card;
      }),
    );
    if (!policies.length)
      $("evidence").append(
        element(
          "p",
          "io-empty",
          "이 계획은 검색 근거를 사용하지 않습니다. RAG 모드에서 근거 기반 정책을 확인할 수 있습니다.",
        ),
      );
  }
  $("target-outcomes").replaceChildren(
    ...(run.plan.targets || [run.plan.target]).map((target) => {
      const steps = run.steps.filter(
        (s) =>
          (run.plan.steps[s.position].target || run.plan.target) === target &&
          s.tool !== "join",
      );
      const state = steps.some((s) => s.status === "failed")
        ? "failed"
        : steps.every((s) => s.status === "succeeded")
          ? "succeeded"
          : terminalStates.includes(run.status)
            ? run.status
            : "pending";
      return element(
        "span",
        `badge ${state}`,
        `${target} · ${statusLabel(state)}`,
      );
    }),
  );
}
function showRun(run) {
  current = run;
  $("empty-state").hidden = true;
  $("run-detail").hidden = false;
  $("run-status").className = `badge ${run.status}`;
  $("run-status").textContent = statusLabel(run.status);
  $("inspector-title").textContent = run.goal;
  $("run-target").textContent = run.plan.target;
  $("run-id").textContent = run.id.slice(0, 12);
  $("run-id").title = run.id;
  const interpretation = run.plan.interpretation;
  $("run-model").hidden = !interpretation;
  $("run-model").textContent = interpretation
    ? `${interpretation.model} · 계획 생성 ${(interpretation.latency_ms / 1000).toFixed(1)}초`
    : "";
  $("run-scenario").textContent =
    `시뮬레이션: ${{ none: "정상 실행", transient: "한 번 실패한 뒤 재시도 성공", persistent: "재시도 한도 소진", verification: "무결성 검증 실패" }[run.plan.failure]}${run.plan.failure_target && run.plan.failure !== "none" ? ` · ${run.plan.failure_target}에만 적용` : ""}`;
  $("step-count").textContent = `${run.steps.length}`;
  $("steps").replaceChildren(
    ...run.steps.map((step, index) => {
      const li = element("li");
      const button = element("button", `step-node ${step.status}`);
      const symbol = element("span", "step-kind");
      symbol.append(
        icon(
          step.status === "succeeded"
            ? "check-circle"
            : step.status === "failed"
              ? "warning"
              : step.tool === "join"
                ? "workflow"
                : "server",
        ),
      );
      const copy = element("span", "step-copy");
      copy.append(
        element("strong", "", tools[step.tool] || "실행 단계"),
        element(
          "small",
          "",
          `${run.plan.steps[index].target || run.plan.target} · ${statusLabel(step.status)}`,
        ),
      );
      button.append(symbol, copy);
      button.addEventListener("click", () => {
        selectedStep = index;
        activateTab("execution");
        showStep();
      });
      li.append(button);
      return li;
    }),
  );
  $("approval").hidden = run.status !== "awaiting_approval";
  const terminal = terminalStates.includes(run.status);
  $("cancel").hidden = terminal || run.status === "awaiting_approval";
  $("outcome").hidden = !terminal;
  $("outcome").className = `outcome ${run.status}`;
  $("outcome").textContent =
    {
      succeeded: "모든 대상의 모의 실행과 검증이 완료되었습니다.",
      failed:
        "실행에 실패했습니다. 이벤트에서 실패 단계와 재시도 기록을 확인하세요.",
      partial_failure:
        "일부 대상이 실패했습니다. 성공한 대상의 결과는 보존되었습니다.",
      rejected: "계획을 거절했습니다. 실행된 단계는 없습니다.",
      cancelled:
        "남은 작업을 취소했습니다. 이미 완료한 작업 기록은 보존됩니다.",
    }[run.status] || "";
  $("result-json").textContent = JSON.stringify(run, null, 2);
  showEvidence(run);
  showStep();
}
const eventLabels = {
  plan_created: "계획 생성",
  model_interpreted: "요청 해석",
  awaiting_approval: "승인 대기",
  queued: "실행 대기",
  approved: "승인",
  rejected: "거절",
  running: "실행 시작",
  step_started: "단계 시작",
  step_completed: "단계 완료",
  step_skipped: "단계 생략",
  retry_scheduled: "재시도 예약",
  branch_failed: "대상 실패",
  succeeded: "실행 성공",
  failed: "실행 실패",
  partial_failure: "부분 실패",
  cancelled: "작업 취소",
};
function eventMessage(event) {
  const p = event.payload;
  const step = current?.steps[p.position];
  const label = step ? stepName(current, step) : "";
  return (
    {
      plan_created: "검증된 요청으로 실행 계획을 생성했습니다.",
      model_interpreted: "로컬 모델이 요청의 작업과 대상을 해석했습니다.",
      awaiting_approval: "계획을 검토하고 실행 여부를 결정하세요.",
      queued: "실행 순서를 기다리고 있습니다.",
      approved: "표시된 계획에 승인이 연결되었습니다.",
      rejected: "계획을 거절했습니다. 단계를 실행하지 않습니다.",
      running: "모의 실행을 시작했습니다.",
      step_started: `${label} · ${p.attempt}회차`,
      step_completed: `${label} · 완료`,
      step_skipped: `${label} · 선행 단계 실패로 건너뜁니다.`,
      retry_scheduled: `${label} · 일시 실패, ${p.attempt}/${p.max_attempts}회 시도`,
      branch_failed: `${p.target || ""} · ${/budget/.test(p.message || "") ? "재시도 한도를 소진했습니다." : "검증에 실패했습니다."}`,
      succeeded: "모든 모의 검증을 통과했습니다.",
      failed: /budget/.test(p.message || "")
        ? "재시도 한도를 소진했습니다."
        : "검증에 실패했습니다.",
      partial_failure: "대상별 성공과 실패 결과를 합산했습니다.",
      cancelled: "남은 단계를 중단하고 완료 기록을 보존했습니다.",
    }[event.kind] || "실행 상태가 갱신되었습니다."
  );
}
function showEvents() {
  const sorted = [...events.values()].sort((a, b) => a.seq - b.seq);
  $("event-count").textContent = sorted.length;
  $("trace").replaceChildren(
    ...sorted.map((event) => {
      const row = element("div", `event ${event.kind}`);
      row.append(
        element(
          "time",
          "mono",
          new Date(event.created_at).toLocaleTimeString("ko-KR", {
            hour12: false,
          }),
        ),
        element("strong", "event-kind", eventLabels[event.kind] || "상태 변경"),
        element("span", "event-message", eventMessage(event)),
      );
      return row;
    }),
  );
}
async function history() {
  recentRuns = await api("/api/runs");
  $("metric-total").textContent = $("nav-total").textContent =
    recentRuns.length;
  $("metric-pending").textContent = recentRuns.filter(
    (r) => r.status === "awaiting_approval",
  ).length;
  $("metric-success").textContent = recentRuns.filter(
    (r) => r.status === "succeeded",
  ).length;
  $("metric-failed").textContent = recentRuns.filter((r) =>
    ["failed", "partial_failure"].includes(r.status),
  ).length;
  showTable();
  showAnalytics();
  return recentRuns;
}
async function selectRun(id, open = true) {
  const generation = ++selection;
  if (source) source.close();
  clearTimeout(refreshTimer);
  const [run, trace] = await Promise.all([
    api(`/api/runs/${id}`),
    api(`/api/runs/${id}/events`),
  ]);
  if (generation !== selection) return;
  selectedStep = 0;
  events = new Map(trace.map((e) => [e.seq, e]));
  showRun(run);
  showEvents();
  if (open) openDialog("inspector-dialog");
  await history();
  if (generation !== selection || terminalStates.includes(run.status)) return;
  const stream = new EventSource(
    `/api/runs/${id}/stream?after=${Math.max(0, ...events.keys())}`,
  );
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
      } catch (e) {
        notice(e.message);
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
  $("form-error").hidden = true;
  $("create").disabled = true;
  $("create").textContent =
    plannerMode === "rag"
      ? "근거 검색·정책 검증 중…"
      : plannerMode === "ollama"
        ? "로컬 모델로 해석 중…"
        : "계획 생성 중…";
  try {
    const run = await api("/api/runs", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        goal: $("goal").value,
        failure: $("failure").value,
      }),
    });
    $("compose-dialog").close();
    await selectRun(run.id);
    activateTab("execution");
  } catch (e) {
    $("form-error").textContent = e.message;
    $("form-error").hidden = false;
  } finally {
    $("create").disabled = false;
    $("create").replaceChildren(
      document.createTextNode("계획 생성"),
      icon("arrow"),
    );
  }
});
for (const decision of ["approve", "reject", "cancel"])
  $(decision).addEventListener("click", async () => {
    if (!current) return;
    const generation = selection;
    ["approve", "reject", "cancel"].forEach((id) => ($(id).disabled = true));
    try {
      const run = await api(`/api/runs/${current.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, plan_hash: current.plan.hash }),
      });
      if (generation === selection) showRun(run);
      await history();
    } catch (e) {
      notice(e.message);
    } finally {
      ["approve", "reject", "cancel"].forEach((id) => ($(id).disabled = false));
    }
  });
const tabs = [...document.querySelectorAll("[data-view]")];
function activateTab(view) {
  tabs.forEach((tab) => {
    const selected = tab.dataset.view === view;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    $(`view-${tab.dataset.view}`).hidden = !selected;
  });
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.view));
  tab.addEventListener("keydown", (event) => {
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
document
  .querySelectorAll("[data-page]")
  .forEach((b) => b.addEventListener("click", () => setPage(b.dataset.page)));
document.querySelectorAll("[data-compose]").forEach((b) =>
  b.addEventListener("click", () => {
    document.body.classList.remove("mobile-nav");
    openDialog("compose-dialog");
    $("goal").focus();
  }),
);
document
  .querySelectorAll("[data-close]")
  .forEach((b) =>
    b.addEventListener("click", () => $(b.dataset.close).close()),
  );
document.querySelectorAll("dialog").forEach((d) =>
  d.addEventListener("click", (e) => {
    if (e.target === d) {
      const r = d.getBoundingClientRect();
      if (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      )
        d.close();
    }
  }),
);
document
  .querySelectorAll("[data-filter]")
  .forEach((b) =>
    b.addEventListener("click", () => setFilter(b.dataset.filter)),
  );
document.querySelectorAll("[data-metric]").forEach((b) =>
  b.addEventListener("click", () => {
    setPage("runs");
    setFilter(b.dataset.metric);
  }),
);
document.querySelectorAll("[data-goal]").forEach((b) =>
  b.addEventListener("click", () => {
    $("goal").value = b.dataset.goal;
    if (b.dataset.goal === "서버 목록 보여줘") $("failure").value = "none";
    $("goal").focus();
  }),
);
$("run-search").addEventListener("input", showTable);
$("refresh").addEventListener("click", () =>
  history().catch((e) => notice(e.message)),
);
$("attention-banner").addEventListener("click", () => {
  $("run-search").value = "";
  setPage("runs");
  setFilter("attention");
});
$("open-trace").addEventListener("click", () => {
  if (!current) {
    notice("먼저 실행 목록에서 워크플로를 선택하세요.");
    setPage("runs");
    return;
  }
  openDialog("inspector-dialog");
  activateTab("trace");
});
$("sidebar-toggle").addEventListener("click", () => {
  const mobile = matchMedia("(max-width: 767px)").matches;
  document.body.classList.toggle(mobile ? "mobile-nav" : "sidebar-collapsed");
  const open = mobile
    ? document.body.classList.contains("mobile-nav")
    : !document.body.classList.contains("sidebar-collapsed");
  $("sidebar-toggle").setAttribute("aria-expanded", String(open));
  $("sidebar-toggle").setAttribute(
    "aria-label",
    open ? "사이드바 접기" : "사이드바 펼치기",
  );
});
try {
  document.documentElement.dataset.theme =
    localStorage.getItem("ops-theme") || "light";
} catch {}
$("theme").addEventListener("click", () => {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("ops-theme", theme);
  } catch {}
});
async function init() {
  const health = await api("/api/health");
  plannerMode = health.planner;
  if (plannerMode !== "deterministic") {
    $("planner-label").textContent =
      plannerMode === "rag" ? "근거 기반 계획 그래프" : "로컬 LLM 계획";
    $("planner-description").textContent = [
      health.model,
      health.embedding_model,
    ]
      .filter(Boolean)
      .join(" + ");
    $("planner-tag").textContent =
      plannerMode === "rag" ? "RAG · 다중 대상" : "Ollama";
    $("planner-help").textContent =
      plannerMode === "rag"
        ? "하나의 작업과 최대 세 대상 이름을 입력하세요. 근거와 정책을 검토한 뒤 전체 계획을 승인합니다. 실패 시나리오는 첫 번째 대상에만 적용됩니다."
        : "한국어나 영어로 작업 하나와 가상 대상 이름을 입력하세요. 로컬 모델이 제안한 계획을 검토하고 승인합니다.";
    $("batch-preset").hidden = plannerMode !== "rag";
  }
  const targets = await api("/api/targets");
  $("targets").replaceChildren(
    ...targets.map((t) => {
      const row = element("div", "target");
      const avatar = element("span", "agent-avatar");
      avatar.append(icon("server"));
      const copy = element("span");
      copy.append(
        element("strong", "", t.id),
        element(
          "small",
          "",
          {
            Application: "애플리케이션",
            Database: "데이터베이스",
            Worker: "작업 처리 서버",
          }[t.role],
        ),
      );
      row.append(avatar, copy, element("span", "badge succeeded", "정상"));
      return row;
    }),
  );
  const runs = await history();
  if (runs.length) await selectRun(runs[0].id, false);
}
init().catch((e) => notice(e.message));

// Keep collapsed navigation named for keyboard and assistive technology users.
document
  .querySelectorAll(".sidebar nav button, .sidebar nav a")
  .forEach((node) => {
    const label =
      node.querySelector("span")?.textContent || node.textContent.trim();
    node.setAttribute("aria-label", label);
    node.title = label;
  });
const mobileLayout = matchMedia("(max-width: 767px)");
function resetSidebarForViewport() {
  if (mobileLayout.matches)
    document.body.classList.remove("sidebar-collapsed", "mobile-nav");
  const expanded =
    !mobileLayout.matches &&
    !document.body.classList.contains("sidebar-collapsed");
  $("sidebar-toggle").setAttribute("aria-expanded", String(expanded));
  $("sidebar-toggle").setAttribute(
    "aria-label",
    expanded ? "사이드바 접기" : "사이드바 펼치기",
  );
}
mobileLayout.addEventListener("change", resetSidebarForViewport);
resetSidebarForViewport();
document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    document.body.classList.contains("mobile-nav")
  ) {
    document.body.classList.remove("mobile-nav");
    $("sidebar-toggle").setAttribute("aria-expanded", "false");
    $("sidebar-toggle").focus();
  }
});
