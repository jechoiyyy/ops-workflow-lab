"""Official MCP SDK stdio interface; human decisions remain in the local UI/API."""

import os

from mcp.server.fastmcp import FastMCP

from .engine import Engine
from .llm import OllamaPlanner
from .planner import TARGETS
from .store import Store


def build_server(db_path: str | None = None) -> FastMCP:
    store = Store(db_path or os.environ.get("OPS_LAB_DB", ".data/lab.db"))
    mode = os.environ.get("OPS_LAB_PLANNER", "deterministic")
    if mode not in {"deterministic", "ollama"}:
        raise ValueError("OPS_LAB_PLANNER must be deterministic or ollama.")
    planner = OllamaPlanner(os.environ.get("OPS_LAB_MODEL", "")) if mode == "ollama" else None
    engine = Engine(store, planner=planner) if planner else Engine(store)
    server = FastMCP("Ops Workflow Lab")

    @server.tool()
    def list_demo_targets() -> list[dict]:
        """List fictional targets. This tool does not access real infrastructure."""
        return TARGETS

    @server.tool()
    def propose_workflow(goal: str, request_key: str, failure: str = "none") -> dict:
        """Propose a demo plan. Writes require approval in the local UI.

        Use a unique request_key (8–128 letters, digits, underscores or dashes).
        Retry the same request with the same key. Keep the UI server running
        against the same database for execution. Example goal: Back up atlas-api.
        """
        return engine.create(goal, failure, request_key)

    @server.tool()
    def get_workflow(run_id: str) -> dict:
        """Read the durable state of a synthetic workflow."""
        return store.get(run_id)

    @server.tool()
    def get_workflow_events(run_id: str, after: int = 0) -> list[dict]:
        """Replay persisted events after a sequence number."""
        return store.events(run_id, after)

    return server


def main():
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
