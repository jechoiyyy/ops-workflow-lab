# Ops Workflow Lab

[한국어](docs/README.ko.md) · [Architecture](docs/architecture.md) · [Design decisions](docs/design-decisions.md) · [Public-release scope](docs/public-release.md)

A runnable operations-agent portfolio demo: review a plan, approve simulated changes, and follow every execution step in a durable event timeline.

**All infrastructure and results are synthetic.** The planner uses a small, explicit command grammar, not an LLM. No API key, cloud account, or external service is needed at runtime.

> Independent demonstration implementation. No company source code, product API contracts, internal runbooks, credentials, customer data, or original Git history are included.

![Workflow studio showing an approval-gated plan](docs/workflow-studio.png)

## Run locally

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/jechoiyyy/ops-workflow-lab.git
cd ops-workflow-lab
uv sync --frozen --extra dev
uv run ops-lab
```

Open **http://127.0.0.1:8765**. The server binds to loopback. Run state is stored in the ignored `.data/lab.db` file and survives restarts. Dependencies are downloaded during setup; the running demo does not need internet access.

For a separate workspace: `uv run ops-lab --port 8766 --db .data/second.db`.

## Try a two-minute walkthrough

1. Enter **Back up atlas-api** and select **Timeout once, then recover**.
2. Build the execution plan. All tool attempts remain at zero while approval is pending.
3. Review the target, scenario, and three planned steps, then approve.
4. Watch the synthetic snapshot fail once, retry, and pass verification. Expand the JSON result to inspect the receipt.
5. Create another plan and reject it, or choose **Exhaust the retry budget** to inspect a controlled failure.

| Example request | What happens |
| --- | --- |
| `Show inventory` | Reads three fictional servers; no approval required |
| `Back up atlas-api` | Inspects a fictional server, creates a simulated snapshot, verifies it |
| `Rehearse recovery for lumen-db` | Creates and verifies a simulated sandbox after approval |
| `atlas-api 백업해줘` | Korean equivalent of the backup request |
| `lumen-db 복구 리허설해줘` | Korean equivalent of the rehearsal request |

Targets are `atlas-api`, `lumen-db`, and `cedar-worker`. The planner intentionally rejects unknown targets, ambiguous phrasing, and compound commands instead of guessing.

## What this demonstrates

- **Approval bound to a plan:** a SHA-256 digest covers the target, action, steps, and failure scenario. Execution checks the recorded approval again.
- **Idempotent requests:** a unique request key returns the original run on retry. Reusing it with different input returns a conflict.
- **Transactional progress:** a simulated operation receipt, step result, and completion event commit together in SQLite.
- **Bounded failure handling:** transient errors retry up to three total attempts; integrity failures stop immediately.
- **Restart and replay:** completed steps are preserved, queued work resumes, and SSE reconnects use persisted event sequence numbers.
- **MCP interface:** a real stdio server exposes synthetic inventory, proposal, status, and event tools. It does not expose an approval tool.

## Architecture at a glance

```mermaid
flowchart LR
    UI[Local browser UI] --> API[FastAPI]
    HOST[MCP host] --> MCP[Official SDK / stdio]
    API --> ENGINE[Plan and approval engine]
    MCP --> ENGINE
    ENGINE --> DB[(SQLite state and events)]
    WORKER[Local worker] --> ENGINE
    ENGINE --> SIM[Synthetic provider]
    DB --> SSE[SSE event replay]
    SSE --> UI
```

The browser/API and MCP share the application engine and database. The browser's worker executes queued runs. The internal simulator is called directly; the browser does **not** call the simulator through MCP. See [architecture and boundaries](docs/architecture.md).

## Connect an MCP client

Keep the UI server running. Configure a stdio client using the same checkout and database:

```json
{
  "mcpServers": {
    "ops-workflow-lab": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ops-workflow-lab", "run", "ops-lab-mcp"]
    }
  }
}
```

The placeholder path must point to your checkout. If the UI uses a custom database, set the same absolute `OPS_LAB_DB` environment variable in both processes. Available tools: `list_demo_targets`, `propose_workflow`, `get_workflow`, `get_workflow_events`. Refresh the UI's recent-runs list to review a proposal created by an MCP host. Human decisions are made in the local UI/API.

The dependency is deliberately constrained to the supported MCP SDK 1.x API, with an exact resolution in `uv.lock`. [Official SDK documentation](https://py.sdk.modelcontextprotocol.io/v1/).

## Validate

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
python3 scripts/check_public_export.py
```

Tests cover the approval boundary, contradictory decisions, concurrent duplicates, bounded retries, restart recovery, transactional rollback, event replay, HTTP validation, and a real MCP subprocess handshake/tool call.

The local [API reference](http://127.0.0.1:8765/docs) and [OpenAPI schema](http://127.0.0.1:8765/openapi.json) are served without CDN assets.

## Scope and limitations

This is an independently implemented **portfolio demonstration**, not an anonymized production release or a performance benchmark. It contains no actual backup, recovery, cloud provisioning, or product-specific implementation. The read-only inventory and verification outputs are simulated too.

The request interpreter is deterministic; there is no trained classifier, RAG corpus, or LLM integration. The application is local and single-user, with no authentication or multi-tenant authorization. Its approval gate demonstrates a workflow invariant; it does not authenticate the human making the HTTP request. Do not expose it as a public service without adding those controls.

SQLite serializes the demo's immediate tool operations. The atomicity guarantees apply to these in-process simulations, not to real remote infrastructure. External adapters would need remote idempotency, leases, timeouts, and reconciliation. See the [design tradeoffs](docs/design-decisions.md).

## License

MIT for this independently authored demo. Third-party packages retain their own licenses; none of their source trees are vendored here.
