"""A deliberately small, deterministic command grammar; no LLM or external API."""

import hashlib
import json
import re

TARGETS = [
    {"id": "atlas-api", "role": "Application", "region": "demo-west", "state": "healthy"},
    {"id": "lumen-db", "role": "Database", "region": "demo-east", "state": "healthy"},
    {"id": "cedar-worker", "role": "Worker", "region": "demo-west", "state": "healthy"},
]
FAILURES = {"none", "transient", "persistent", "verification"}


class InvalidRequest(ValueError):
    pass


class Conflict(ValueError):
    pass


class NotFound(ValueError):
    pass


class PlannerUnavailable(ValueError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def plan(goal: str, failure: str = "none") -> dict:
    if failure not in FAILURES:
        raise InvalidRequest("Unknown failure scenario.")
    text = " ".join(goal.strip().lower().split()).rstrip(".!")
    if text in {"show inventory", "list servers", "서버 목록 보여줘", "서버 목록"}:
        if failure != "none":
            raise InvalidRequest("Failure injection applies to backup or rehearsal runs.")
        action, target = "inventory", "all"
    else:
        target_pattern = "(" + "|".join(re.escape(t["id"]) for t in TARGETS) + ")"
        patterns = [
            ("backup", rf"(?:back up|backup) {target_pattern}"),
            ("backup", rf"{target_pattern} 백업(?:해줘)?"),
            ("rehearsal", rf"rehearse recovery for {target_pattern}"),
            ("rehearsal", rf"{target_pattern} 복구 리허설(?:해줘)?"),
        ]
        match = next(
            ((a, re.fullmatch(p, text)) for a, p in patterns if re.fullmatch(p, text)), None
        )
        if not match:
            raise InvalidRequest(
                "Use 'Show inventory', 'Back up atlas-api', or "
                "'Rehearse recovery for lumen-db'. Only the three synthetic targets are supported."
            )
        action, parsed = match
        target = parsed.group(1)
    return build_plan(action, target, failure)


def build_plan(action: str, target: str, failure: str = "none") -> dict:
    """Server-owned tool selection; callers can never supply arbitrary steps."""
    if action not in {"inventory", "backup", "rehearsal"} or failure not in FAILURES:
        raise InvalidRequest("Unsupported action or failure scenario.")
    if action == "inventory":
        if target != "all" or failure != "none":
            raise InvalidRequest("Inventory requires target=all and failure=none.")
        steps = [{"tool": "inventory", "title": "Read synthetic inventory", "effect": "read"}]
    else:
        if target not in {item["id"] for item in TARGETS}:
            raise InvalidRequest("Unknown synthetic target.")
        steps = [
            {"tool": "inspect", "title": "Inspect synthetic target", "effect": "read"},
            {
                "tool": "snapshot" if action == "backup" else "sandbox",
                "title": "Create simulated snapshot"
                if action == "backup"
                else "Create rehearsal sandbox",
                "effect": "simulated_write",
            },
            {"tool": "verify", "title": "Verify simulated result", "effect": "read"},
        ]
    proposal = {"action": action, "target": target, "failure": failure, "steps": steps}
    return {**proposal, "hash": digest(proposal), "requires_approval": action != "inventory"}
