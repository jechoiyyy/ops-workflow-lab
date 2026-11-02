# From model intent to inspectable execution

**Role focus: AI Agent / LLM Engineer.** This case study connects my work in a private team infrastructure-automation project to a separate, runnable public demonstration. The public implementation and synthetic results are independently authored. They are not the original product or proof of its production performance.

## Problem and my contribution

An operations assistant must turn a request into a reviewable plan, retain the right evidence for each target, wait for approval and explain what actually happened. A plausible model response is insufficient: execution needs explicit scope, state and failure handling.

My authored changes in the team project covered dense retrieval for tool discovery, graph orchestration and persistence, multi-target workflow handling, passing assessment context into retrieval, separating policy output from executable drafts, and approval/outcome regression coverage. These responsibilities were checked against authored commits and their changes during the portfolio review. Private commit identifiers, implementation contracts and source are deliberately excluded from this repository.

This was collaborative work. I do not claim sole authorship of the complete agent system, all retrieval/prompt work, monitoring or the underlying infrastructure product. The table below distinguishes those experiences from what a reviewer can execute in this independent demo.

| Engineering responsibility | Public demonstration | What a reviewer can verify |
| --- | --- | --- |
| Connect retrieval to an agent workflow | Original synthetic runbooks, local dense embeddings, role/action filtering | `retrieval.py`, corpus version/hash and source scores in Evidence |
| Coordinate per-target planning | LangGraph map/reduce with a nested policy-generation graph | `grounded.py`, persisted node records and bounded repair tests |
| Separate generated policy from execution | Citation and required-control validation; server-built steps | `check_policy`, `compile_dag`; invalid policy creates no approvable run |
| Handle multi-target approval and outcomes | One approval for the complete DAG; independent target chains and final join | `engine.py`, partial-failure and restart tests |
| Make failures inspectable | Durable events, bounded retries, cancellation, operation receipts | UI trace, JSON result, API replay and concurrent-request tests |

Dense **tool** discovery in the private project and **runbook** retrieval in this demo are different scopes. The public demo does not reproduce private tool definitions, tool-selection logic, storage/recovery algorithms or product integrations.

## Decisions that matter

1. **Treat generated output as a proposal.** The model classifies one supported action and selects controls from retrieved evidence. The server verifies target preservation, citation membership and required controls. Model-provided commands and arbitrary execution tools are outside the schema.
2. **Review a concrete artifact.** The plan digest binds targets, steps, dependencies, failure injection, policy controls, evidence text and corpus identity. Approval applies to that artifact. A changed plan requires a new run.
3. **Preserve partial outcomes.** A failed target skips its dependent work; other branches continue. A final join records each target's result and distinguishes total success from partial failure.
4. **Make the reliability claim narrow and testable.** SQLite commits each immediate simulated operation with its receipt and event. This demonstrates transactional workflow state. It does not solve atomicity for real remote APIs.

## Five-minute review

1. Run the [grounded demo](grounded-workflows.md) with local models, or run `uv run ops-lab` for the deterministic baseline.
2. Propose `Back up atlas-api and lumen-db` in RAG mode. Open **근거**, follow a control's source link and inspect the node trace. Before approval, every execution attempt is zero.
3. Repeat with **재시도 한도 소진**. Approve once; compare `atlas-api` failure with `lumen-db` success and inspect the join result.
4. Run `uv run pytest -q`. Read `tests/test_grounded.py` for fabricated citations, missing evidence, repair limits, dropped targets, restart and cancellation.
5. Inspect the [live model smoke report](evaluation-grounded.json) and its [limitations](grounded-workflows.md#evaluation). The results are reproducible with installed models; tests use deterministic doubles for inference.

## Evidence and honest limits

The public repository demonstrates implementation choices and reproducible synthetic behavior. It does not establish employer outcomes, commercial impact, deployment scale or individual ownership of all team work. No latency reduction, cost savings, incident reduction or production success rate is claimed.

The planning graph is in memory and model calls are serialized. Only completed proposals and execution are durable. The API is local and unauthenticated; its approval gate checks workflow state rather than user identity. Real deployment would require authentication, authorization, worker leases, remote idempotency and reconciliation. The corpus is intentionally too small for a meaningful retrieval benchmark.

## 한국어 소개 문구

> 팀 인프라 자동화 프로젝트에서 검색 연계, 그래프 오케스트레이션·상태 관리, 다중 대상 워크플로, 정책과 실행 계획의 분리, 승인·결과 검증을 구현·개선했습니다. 공개 포트폴리오에서는 회사 코드와 내부 정책을 제외하고 가상 런북 기반 RAG, 정책 검증, 단일 승인과 대상별 실행 결과 합산을 별도로 구현했습니다. 로컬 LLM 평가와 실패·재시작 테스트로 동작을 확인할 수 있습니다.

이 문구는 담당 범위를 설명하며 팀 전체 시스템을 단독 구현했다는 뜻이 아닙니다. 원본 구현과의 동일성이나 실제 서비스 성능을 주장하지 않습니다.
