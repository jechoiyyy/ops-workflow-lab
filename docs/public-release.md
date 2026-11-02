# Public-release scope

This is an independently authored demonstration of generic workflow patterns. Its source was written in a separate directory; source files and Git metadata from the reference project were not copied.

## Included

- A new deterministic planner, optional local Ollama intent classifier, and approval/execution state machine.
- Original synthetic evaluation requests and measured local inference reports; no private data is sent to the model by these evaluations.
- A newly defined SQLite schema and transactional event log.
- Fictional inventory and synthetic failure scenarios.
- A new browser UI and local API, including dashboard metrics derived only from local demo runs.
- An independently authored synthetic runbook corpus, local embedding retrieval and a LangGraph planning pipeline.
- A contribution case study describing generic engineering responsibilities without private implementation details.
- A stdio integration using the official MCP SDK.
- Tests, architecture notes, and screenshots generated from the synthetic demo.

## Excluded

- Company-specific implementation, internal API paths, tool contracts, or workflow policies.
- Credentials, internal hosts, deployment manifests, and production environment files.
- Operational logs, database dumps, classifier training data, and internal knowledge corpora.
- Customer data, original screenshots, presentations, and sales documents.
- Original repository commits, branches, tags, remotes, and author metadata.

## Release checks

`scripts/check_public_export.py` inspects the tracked release files. It restricts file paths and extensions, rejects common secret-bearing artifact types and private-network addresses, and checks for credential-shaped content. It is an additional guard, not a proof that arbitrary files are safe to publish.

Before the initial release, the tracked files and fresh Git history are also inspected with Gitleaks. Runtime databases, virtual environments, test outputs, and logs stay outside the export. Dependency lockfile hashes and deliberately fictional test inputs are expected public content.

Screenshots must show only the synthetic application viewport. Browser profiles, bookmarks, other tabs, desktop content, and original product screens are excluded.

Future changes should preserve this boundary. A real integration belongs in a separately reviewed private implementation; adding one here would require a new disclosure review.
