# Design decisions

## Independent demo instead of a renamed production tree

The portfolio should demonstrate engineering decisions without exposing implementation details belonging to another system. This repository was written as a separate application with a new database schema, fictional tools, synthetic targets, original UI, and fresh Git history. It is not presented as the original application or as evidence of production scale.

## Optional local inference with a deterministic baseline

The default grammar makes workflow tests reproducible and runs without model weights. Optional Ollama inference maps varied Korean/English phrasing to a constrained intent. Both paths use the same server-owned step builder. The model cannot supply code, tool names, approvals, or arbitrary targets. This demonstrates an LLM integration boundary, not general autonomous planning.

The inference response is constrained by a JSON schema and validated again with Pydantic. A changing operation must preserve every explicitly named fictional target. Basic Ollama mode supports one; RAG mode supports up to three. Semantic intent can still be misclassified: human plan review remains necessary, and the live evaluation measures a small set of both accepted and rejected requests.

Inference happens outside SQLite's write transaction, with one in-flight request per planner instance, a finite per-call timeout and explicit 503 errors. Basic intent inference has no repair. RAG policies permit one feedback-driven repair; neither path silently falls back. Separate HTTP/MCP processes have independent inference gates. Replays of persisted request keys return their stored run without another model call. Raw hidden reasoning is neither requested nor persisted.

## Hash-bound decisions instead of a global approved flag

A decision carries the exact displayed plan hash. The digest includes target, action, steps, and injected failure scenario. There is no plan-edit API. A different plan must be a new run with a fresh decision. The hash is an integrity binding, not a signature or proof of the approver's identity.

## SQLite transactions instead of a distributed task queue

For a local demonstration, a transactional store keeps the critical state changes easy to audit. Concurrent requests serialize around updates. After a process restart, the worker scans persisted queued/running runs and continues from the next unfinished step.

The provider has no remote side effects, so a simulated result and its receipt can commit together. Moving actual network calls inside this transaction would be inappropriate: it would hold a global write lock and still could not atomically commit a remote action. A real adapter needs stable remote idempotency keys, short claiming transactions, leases, timeouts, and reconciliation after uncertain outcomes.

## Distinct request and operation idempotency

The client request key prevents duplicate runs from retries and is rejected if the request body changes. An operation key identifies a single planned step. This separation makes the scope of deduplication explicit. There is no claim that two differently keyed requests with the same wording are the same operation.

## Persisted events instead of transient progress messages

Progress is part of the durable transaction, so reconnects and restarts can replay it. The UI receives a live feed, but the authoritative result remains in SQLite. A production event log would additionally need retention, pagination, privacy controls, and potentially tamper evidence; none of those are claimed here.

## A small MCP surface

MCP clients can discover targets, propose a workflow, and inspect state. They cannot approve through an MCP tool. Human review stays in the demo UI/API. This is interface separation for the demonstration; since the HTTP API is unauthenticated, it is not a security boundary against other local applications.

## Intentionally absent

No actual snapshots or recovery, no secret management integration, no customer data, no copied operational policies, no real cloud adapters, no private training corpus and no production performance claims. Small synthetic model evaluation reports are included and labeled with their limits. No fabricated incident statistics or outcome metrics are included in the portfolio.

## Grounded controls and deterministic execution

RAG selects policy controls from original synthetic runbooks. Metadata restricts documents by action, role and lifecycle before cosine ranking. Required-source coverage is checked independently of the model; each selected control must cite a retrieved document that lists it. Missing controls or unsupported citations receive one repair attempt, then planning fails closed. Structured JSON alone would not enforce these relationships.

LangGraph `Send` maps over targets and reduces their policies. The nested policy graph captures retrieval, generation and validation. Local inference uses `max_concurrency=1` to avoid claiming parallel model throughput. The execution engine is a separate persisted DAG; every target has an independent chain and one final join. Branch failure skips descendants, preserving unrelated work. The hash covers policies, evidence text and corpus identity as well as execution steps.

The eight-document corpus is intentionally tiny. Metadata filtering leaves one or two eligible sources, so the reported recall at three is a coverage smoke check, not evidence that dense retrieval outperforms lexical search. A meaningful ranking comparison would require many applicable distractors and a separate held-out query set.
