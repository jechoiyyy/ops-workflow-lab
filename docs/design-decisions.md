# Design decisions

## Independent demo instead of a renamed production tree

The portfolio should demonstrate engineering decisions without exposing implementation details belonging to another system. This repository was written as a separate application with a new database schema, fictional tools, synthetic targets, original UI, and fresh Git history. It is not presented as the original application or as evidence of production scale.

## Explicit commands instead of an LLM dependency

The main question is whether plans, decisions, retries, and state transitions behave correctly. A deterministic grammar makes those paths reproducible, runs without credentials, and clearly rejects unsupported requests. The tradeoff is limited phrasing and no compound planning. An LLM could later propose the same plan format, but validation and approval would remain independent of model output.

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

No actual snapshots or recovery, no secret management integration, no customer data, no copied operational policies, no real cloud adapters, no training corpus, no model evaluation results, no production performance claims. No fabricated incident statistics or outcome metrics are included in the portfolio.
