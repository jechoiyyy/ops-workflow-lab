"""Synthetic tool boundary. Contains no cloud client, shell execution, or network calls."""

from typing import Protocol

from .planner import TARGETS


class TemporaryToolError(Exception):
    pass


class VerificationError(Exception):
    pass


class ToolProvider(Protocol):
    def call(
        self, tool: str, target: str, operation_key: str, attempt: int, failure: str
    ) -> dict: ...


class SyntheticProvider:
    def call(self, tool: str, target: str, operation_key: str, attempt: int, failure: str) -> dict:
        if tool == "inventory":
            return {"servers": TARGETS, "synthetic": True}
        server = next(t for t in TARGETS if t["id"] == target)
        if tool == "inspect":
            return {**server, "synthetic": True}
        if tool in {"snapshot", "sandbox"}:
            if failure == "persistent" or (failure == "transient" and attempt == 1):
                raise TemporaryToolError(
                    "Injected simulator timeout; no external request was made."
                )
            return {
                "resource": f"sim-{tool}-{operation_key[:12]}",
                "target": target,
                "state": "ready",
                "synthetic": True,
            }
        if tool == "verify":
            if failure == "verification":
                raise VerificationError("Injected integrity mismatch in the simulated result.")
            return {"integrity": "passed", "target": target, "synthetic": True}
        raise ValueError("Unsupported tool.")
