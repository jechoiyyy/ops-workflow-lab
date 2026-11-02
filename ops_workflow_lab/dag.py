"""Server-owned execution DAG, independent target branches, and explicit final join."""

from .planner import FAILURES, TARGETS, InvalidRequest, digest


def compile_dag(action: str, targets: list[str], failure: str, policies: list[dict]) -> dict:
    if failure not in FAILURES:
        raise InvalidRequest("Unknown failure scenario.")
    if action not in {"backup", "rehearsal"} or not targets or len(set(targets)) != len(targets):
        raise InvalidRequest("A batch needs one supported action and unique targets.")
    if not set(targets) <= {t["id"] for t in TARGETS}:
        raise InvalidRequest("Unknown synthetic target.")
    by_target = {p["target"]: p for p in policies}
    if set(by_target) != set(targets) or len(policies) != len(targets):
        raise InvalidRequest("Every target needs exactly one verified policy.")
    steps = []
    phases = [
        ("inspect", "Inspect synthetic target", "read"),
        ("apply_policy", "Apply simulated policy controls", "simulated_write"),
        (
            "snapshot" if action == "backup" else "sandbox",
            "Create simulated resource",
            "simulated_write",
        ),
        ("verify", "Verify simulated result", "read"),
    ]
    for phase, (tool, title, effect) in enumerate(phases):
        for target in targets:
            steps.append(
                {
                    "id": f"{target}:{phase}",
                    "target": target,
                    "tool": tool,
                    "title": f"{target} · {title}",
                    "effect": effect,
                    "depends_on": [] if phase == 0 else [f"{target}:{phase - 1}"],
                    "controls": by_target[target]["controls"] if tool == "apply_policy" else [],
                }
            )
    steps.append(
        {
            "id": "join",
            "target": "all",
            "tool": "join",
            "title": "Aggregate target outcomes",
            "effect": "read",
            "depends_on": [f"{t}:3" for t in targets],
            "controls": [],
        }
    )
    proposal = {
        "version": 2,
        "action": action,
        "target": ", ".join(targets),
        "targets": targets,
        "failure": failure,
        "failure_target": targets[0],
        "steps": steps,
        "policies": [by_target[t] for t in targets],
    }
    return {**proposal, "hash": digest(proposal), "requires_approval": True}


def specs(run):
    """Adapt historical linear plans without rewriting their persisted hashes."""
    proposal = run["plan"]
    return [
        {
            "id": str(i),
            "target": proposal["target"],
            "depends_on": [str(i - 1)] if i else [],
            **step,
        }
        for i, step in enumerate(proposal["steps"])
    ]


def outcomes(run):
    definition = specs(run)
    targets = run["plan"].get("targets", [run["plan"]["target"]])
    result = {}
    for target in targets:
        states = [
            run["steps"][i]["status"]
            for i, spec in enumerate(definition)
            if spec["target"] == target and spec["tool"] != "join"
        ]
        result[target] = (
            "failed"
            if "failed" in states
            else "succeeded"
            if states and all(s == "succeeded" for s in states)
            else "cancelled"
            if run["status"] == "cancelled"
            else "pending"
        )
    return result
