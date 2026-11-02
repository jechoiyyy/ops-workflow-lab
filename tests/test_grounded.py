import copy

import pytest
from fastapi.testclient import TestClient

from ops_workflow_lab.dag import outcomes
from ops_workflow_lab.engine import TERMINAL, Engine
from ops_workflow_lab.grounded import GroundedPlanner, check_policy
from ops_workflow_lab.planner import Conflict, InvalidRequest, PlannerUnavailable
from ops_workflow_lab.retrieval import RunbookRetriever
from ops_workflow_lab.server import create_app
from ops_workflow_lab.store import Store


def retriever():
    return RunbookRetriever(embed=lambda texts: [[1.0, 0.5] for _ in texts])


def planner(targets=None, bad_attempts=0):
    targets = targets or ["atlas-api", "lumen-db"]
    attempts = {}

    def generate(schema, system, payload):
        if "request" in payload:
            return {"disposition": "accept", "action": "backup", "targets": targets}
        target = payload["target"]
        attempts[target] = attempts.get(target, 0) + 1
        if attempts[target] <= bad_attempts:
            return {"controls": [{"control": "skip_validation", "source_id": "invented"}]}
        return {
            "controls": [
                {"control": c, "source_id": d["id"]}
                for d in payload["evidence"]
                if d["required"]
                for c in d["controls"]
            ]
        }

    return GroundedPlanner("test-model", retriever=retriever(), generate=generate)


def test_retrieval_excludes_retired_wrong_role_and_wrong_action():
    search = retriever()
    hits = search.search("backup database", "backup", "Database")
    assert {d["id"] for d in hits} == {"backup-core", "backup-database"}
    search.ensure_coverage(hits, "backup", "Database")
    with pytest.raises(InvalidRequest, match="missing"):
        search.ensure_coverage(hits[:1], "backup", "Database")


@pytest.mark.parametrize("vectors", [[[0, 0]], [[float("nan")]], [[True]], [], [[1], [1, 2]]])
def test_invalid_embedding_response_is_closed(vectors):
    with pytest.raises(PlannerUnavailable):
        RunbookRetriever._normalize(vectors, 1)


def test_policy_citations_require_membership_and_complete_controls():
    evidence = retriever().search("backup", "backup", "Database")
    assert check_policy(
        {"controls": [{"control": "pause_writes", "source_id": "backup-core"}]}, evidence
    )
    assert check_policy(
        {"controls": [{"control": "invented", "source_id": "backup-core"}]}, evidence
    )


def test_real_graph_fanout_repairs_once_and_hash_covers_evidence():
    result = planner(bad_attempts=1)("Back up atlas-api and lumen-db")
    assert result["targets"] == ["atlas-api", "lumen-db"]
    assert len(result["steps"]) == 9
    assert all(p["attempts"] == 2 for p in result["policies"])
    assert all(len(p["trace"]) == 5 for p in result["policies"])
    assert result["steps"][-1]["depends_on"] == ["atlas-api:3", "lumen-db:3"]
    original = planner()("Back up atlas-api and lumen-db")
    other = planner()
    other.retriever.documents[0]["text"] += " Revised synthetic evidence."
    assert other("Back up atlas-api and lumen-db")["hash"] != original["hash"]


def test_bad_policy_never_creates_approvable_run(tmp_path):
    engine = Engine(Store(str(tmp_path / "bad.db")), planner=planner(bad_attempts=2))
    with pytest.raises(InvalidRequest, match="two attempts"):
        engine.create("Back up atlas-api and lumen-db", "none", "bad-policy-key")
    assert not engine.store.recent()


def test_model_cannot_silently_drop_a_target():
    with pytest.raises(InvalidRequest, match="preserved"):
        planner(["atlas-api"])("Back up atlas-api and lumen-db")


@pytest.mark.parametrize(
    "failure,expected",
    [
        ("none", "succeeded"),
        ("transient", "succeeded"),
        ("persistent", "partial_failure"),
        ("verification", "partial_failure"),
    ],
)
def test_dag_approval_restart_branch_isolation_and_join(tmp_path, failure, expected):
    path = str(tmp_path / "batch.db")
    engine = Engine(Store(path), planner=planner())
    run = engine.create("Back up atlas-api and lumen-db", failure, "batch-request")
    assert all(s["attempts"] == 0 for s in engine.tick(run["id"])["steps"])
    engine.decide(run["id"], run["plan"]["hash"], "approve")
    engine.tick(run["id"])
    engine = Engine(Store(path))
    for _ in range(20):
        run = engine.tick(run["id"])
        if run["status"] in TERMINAL:
            break
    assert run["status"] == expected
    assert outcomes(run)["lumen-db"] == "succeeded"
    assert run["steps"][-1]["result"]["targets"] == outcomes(run)
    assert run["steps"][0]["attempts"] == 1
    assert engine.tick(run["id"]) == run
    assert sum(e["kind"] == expected for e in engine.store.events(run["id"])) == 1


def test_cancel_retains_completed_receipts_and_is_idempotent(tmp_path):
    engine = Engine(Store(str(tmp_path / "cancel.db")), planner=planner())
    run = engine.create("Back up atlas-api and lumen-db", "none", "cancel-request")
    engine.decide(run["id"], run["plan"]["hash"], "approve")
    first = copy.deepcopy(engine.tick(run["id"])["steps"][0])
    with pytest.raises(Conflict):
        engine.decide(run["id"], "0" * 64, "cancel")
    stopped = engine.decide(run["id"], run["plan"]["hash"], "cancel")
    assert stopped["steps"][0] == first
    assert all(s["status"] == "skipped" for s in stopped["steps"][1:])
    assert engine.tick(run["id"]) == stopped
    assert engine.decide(run["id"], run["plan"]["hash"], "cancel") == stopped


def test_partial_failure_http_snapshot_and_sse_terminate(tmp_path):
    app = create_app(str(tmp_path / "http-batch.db"), planner=planner())
    # Advance manually to keep this integration check independent of worker timing.
    client = TestClient(app)
    run = client.post(
        "/api/runs",
        json={"goal": "Back up atlas-api and lumen-db", "failure": "persistent"},
        headers={"Idempotency-Key": "http-batch-key"},
    ).json()
    assert client.get("/api/health").json()["planner"] == "rag"
    client.post(
        f"/api/runs/{run['id']}/decision",
        json={"decision": "approve", "plan_hash": run["plan"]["hash"]},
    )
    for _ in range(20):
        final = app.state.engine.tick(run["id"])
        if final["status"] in TERMINAL:
            break
    assert final["status"] == "partial_failure"
    response = client.get(f"/api/runs/{run['id']}/stream")
    assert "event: done" in response.text
    assert '"status": "partial_failure"' in response.text


def test_single_target_failure_is_total_and_three_target_join_preserves_results(tmp_path):
    for targets, expected in [
        (["atlas-api"], "failed"),
        (["atlas-api", "lumen-db", "cedar-worker"], "partial_failure"),
    ]:
        engine = Engine(Store(str(tmp_path / f"{len(targets)}.db")), planner=planner(targets))
        run = engine.create("Back up " + " and ".join(targets), "persistent", "target-count-key")
        engine.decide(run["id"], run["plan"]["hash"], "approve")
        for _ in range(30):
            run = engine.tick(run["id"])
            if run["status"] in TERMINAL:
                break
        assert run["status"] == expected
        assert len(run["steps"][-1]["result"]["targets"]) == len(targets)
