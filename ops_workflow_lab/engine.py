"""Durable approval gate and bounded execution for the synthetic provider."""

import json
import re
import uuid

from .planner import Conflict, InvalidRequest, digest, plan
from .provider import SyntheticProvider, TemporaryToolError, ToolProvider, VerificationError
from .store import Store, now

TERMINAL = {"succeeded", "failed", "rejected"}
MAX_ATTEMPTS = 3


class Engine:
    def __init__(self, store: Store, provider: ToolProvider | None = None):
        self.store = store
        self.provider = provider or SyntheticProvider()

    def create(self, goal: str, failure: str, request_key: str) -> dict:
        if not isinstance(goal, str) or not 1 <= len(goal) <= 180:
            raise InvalidRequest("Goal must contain 1 to 180 characters.")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{8,128}", request_key):
            raise InvalidRequest(
                "Idempotency-Key must be 8–128 letters, digits, underscores or dashes."
            )
        proposal = plan(goal, failure)
        fingerprint = digest({"goal": goal, "failure": failure})
        with self.store.transaction() as db:
            existing = db.execute(
                "SELECT * FROM runs WHERE request_key=?", (request_key,)
            ).fetchone()
            if existing:
                if existing["fingerprint"] != fingerprint:
                    raise Conflict("This idempotency key is already bound to a different request.")
                return self.store.snapshot(db, existing["id"])
            run_id = uuid.uuid4().hex
            status = "awaiting_approval" if proposal["requires_approval"] else "queued"
            db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)",
                (run_id, request_key, fingerprint, goal, json.dumps(proposal), status, None, now()),
            )
            db.executemany(
                "INSERT INTO steps(run_id,position,tool,title) VALUES(?,?,?,?)",
                [(run_id, i, s["tool"], s["title"]) for i, s in enumerate(proposal["steps"])],
            )
            self.store.event(
                db,
                run_id,
                "plan_created",
                message="Validated deterministic plan.",
                plan_hash=proposal["hash"],
            )
            self.store.event(
                db,
                run_id,
                status,
                message=(
                    "Review the plan before approving simulated changes."
                    if proposal["requires_approval"]
                    else "Read-only inventory queued."
                ),
            )
            return self.store.snapshot(db, run_id)

    def decide(self, run_id: str, plan_hash: str, decision: str) -> dict:
        if decision not in {"approve", "reject"}:
            raise InvalidRequest("Decision must be approve or reject.")
        with self.store.transaction() as db:
            run = self.store.snapshot(db, run_id)
            if plan_hash != run["plan"]["hash"]:
                raise Conflict("The decision does not match the displayed plan.")
            if not run["plan"]["requires_approval"]:
                raise Conflict("This read-only run does not require a decision.")
            if run["status"] != "awaiting_approval":
                if (decision == "approve" and run["approved_hash"] == plan_hash) or (
                    decision == "reject" and run["status"] == "rejected"
                ):
                    return run
                raise Conflict("The run already has a different decision.")
            status = "queued" if decision == "approve" else "rejected"
            db.execute(
                "UPDATE runs SET status=?,approved_hash=? WHERE id=?",
                (
                    status,
                    plan_hash if decision == "approve" else None,
                    run_id,
                ),
            )
            if decision == "reject":
                db.execute("UPDATE steps SET status='skipped' WHERE run_id=?", (run_id,))
            self.store.event(
                db,
                run_id,
                "approved" if decision == "approve" else "rejected",
                message="Plan approved." if decision == "approve" else "Plan rejected.",
                plan_hash=plan_hash,
            )
            return self.store.snapshot(db, run_id)

    def tick(self, run_id: str) -> dict:
        # Synthetic calls are immediate and have no external side effects. Their result,
        # operation receipt and completion event commit atomically with the step.
        with self.store.transaction() as db:
            run = self.store.snapshot(db, run_id)
            if run["status"] not in {"queued", "running"}:
                return run
            proposal = run["plan"]
            if proposal["requires_approval"] and run["approved_hash"] != proposal["hash"]:
                raise Conflict("A matching approval is required for execution.")
            if run["status"] == "queued":
                db.execute("UPDATE runs SET status='running' WHERE id=?", (run_id,))
                self.store.event(db, run_id, "running", message="Execution started.")
            step = next((s for s in run["steps"] if s["status"] in {"pending", "retrying"}), None)
            if step is None:
                return self.store.snapshot(db, run_id)
            attempt = step["attempts"] + 1
            position = step["position"]
            key = digest({"run": run_id, "position": position, "plan": proposal["hash"]})
            self.store.event(
                db,
                run_id,
                "step_started",
                message=step["title"],
                position=position,
                attempt=attempt,
            )
            db.execute(
                "UPDATE steps SET attempts=? WHERE run_id=? AND position=?",
                (attempt, run_id, position),
            )
            try:
                receipt = db.execute("SELECT result FROM operations WHERE key=?", (key,)).fetchone()
                result = (
                    json.loads(receipt[0])
                    if receipt
                    else self.provider.call(
                        step["tool"], proposal["target"], key, attempt, proposal["failure"]
                    )
                )
            except TemporaryToolError as exc:
                if attempt < MAX_ATTEMPTS:
                    db.execute(
                        "UPDATE steps SET status='retrying' WHERE run_id=? AND position=?",
                        (run_id, position),
                    )
                    self.store.event(
                        db,
                        run_id,
                        "retry_scheduled",
                        message=str(exc),
                        position=position,
                        attempt=attempt,
                        max_attempts=MAX_ATTEMPTS,
                    )
                else:
                    self._fail(db, run_id, position, "Retry budget exhausted.")
            except VerificationError as exc:
                self._fail(db, run_id, position, str(exc))
            else:
                data = json.dumps(result)
                db.execute("INSERT OR IGNORE INTO operations VALUES(?,?,?)", (key, run_id, data))
                db.execute(
                    "UPDATE steps SET status='succeeded',result=? WHERE run_id=? AND position=?",
                    (data, run_id, position),
                )
                self.store.event(
                    db,
                    run_id,
                    "step_completed",
                    message=step["title"],
                    position=position,
                    attempt=attempt,
                    result=result,
                )
                if position == len(run["steps"]) - 1:
                    db.execute("UPDATE runs SET status='succeeded' WHERE id=?", (run_id,))
                    self.store.event(
                        db, run_id, "succeeded", message="All simulated checks passed."
                    )
            return self.store.snapshot(db, run_id)

    def _fail(self, db, run_id: str, position: int, message: str):
        db.execute(
            "UPDATE steps SET status='failed' WHERE run_id=? AND position=?", (run_id, position)
        )
        db.execute(
            "UPDATE steps SET status='skipped' WHERE run_id=? AND position>?", (run_id, position)
        )
        db.execute("UPDATE runs SET status='failed' WHERE id=?", (run_id,))
        self.store.event(db, run_id, "failed", message=message, position=position)
