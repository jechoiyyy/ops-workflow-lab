from concurrent.futures import ThreadPoolExecutor

import pytest

from ops_workflow_lab.engine import Engine
from ops_workflow_lab.planner import Conflict, InvalidRequest, plan
from ops_workflow_lab.store import Store


@pytest.fixture
def engine(tmp_path):
    return Engine(Store(str(tmp_path / "test.db")))


def create(engine, failure="none", key="request-001", goal="Back up atlas-api"):
    return engine.create(goal, failure, key)


def approve(engine, run):
    return engine.decide(run["id"], run["plan"]["hash"], "approve")


def finish(engine, run):
    for _ in range(10):
        run = engine.tick(run["id"])
        if run["status"] in {"succeeded", "failed", "rejected"}:
            return run
    pytest.fail("Run did not terminate within the expected step budget.")


def test_approval_is_required_even_if_tick_is_called_directly(engine):
    run = create(engine)
    for _ in range(3):
        run = engine.tick(run["id"])
    assert run["status"] == "awaiting_approval"
    assert all(step["attempts"] == 0 for step in run["steps"])
    assert not any(e["kind"] == "step_started" for e in engine.store.events(run["id"]))


def test_approval_binds_to_exact_plan_and_cannot_be_reversed(engine):
    run = create(engine)
    with pytest.raises(Conflict):
        engine.decide(run["id"], "0" * 64, "approve")
    approve(engine, run)
    with pytest.raises(Conflict):
        engine.decide(run["id"], run["plan"]["hash"], "reject")
    assert approve(engine, run)["status"] == "queued"
    assert sum(e["kind"] == "approved" for e in engine.store.events(run["id"])) == 1


def test_rejection_is_terminal_and_runs_no_tools(engine):
    run = create(engine)
    engine.decide(run["id"], run["plan"]["hash"], "reject")
    result = finish(engine, run)
    assert result["status"] == "rejected"
    assert all(s["status"] == "skipped" and s["attempts"] == 0 for s in result["steps"])
    with pytest.raises(Conflict):
        approve(engine, run)


def test_idempotency_reuses_run_but_rejects_changed_payload(engine):
    run = create(engine)
    assert create(engine)["id"] == run["id"]
    with pytest.raises(Conflict):
        create(engine, failure="transient")


def test_concurrent_creation_approval_and_execution(engine):
    with ThreadPoolExecutor(max_workers=6) as pool:
        runs = list(pool.map(lambda _: create(engine), range(12)))
        assert len({r["id"] for r in runs}) == 1
        run = runs[0]
        list(pool.map(lambda _: approve(engine, run), range(12)))
        list(pool.map(lambda _: engine.tick(run["id"]), range(16)))
    result = engine.store.get(run["id"])
    assert result["status"] == "succeeded"
    assert [s["attempts"] for s in result["steps"]] == [1, 1, 1]
    with engine.store.transaction() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 3
    assert sum(e["kind"] == "succeeded" for e in engine.store.events(run["id"])) == 1


@pytest.mark.parametrize(
    "failure,expected,attempts",
    [
        ("none", "succeeded", [1, 1, 1]),
        ("transient", "succeeded", [1, 2, 1]),
        ("persistent", "failed", [1, 3, 0]),
        ("verification", "failed", [1, 1, 1]),
    ],
)
def test_failure_scenarios(engine, failure, expected, attempts):
    run = create(engine, failure=failure)
    approve(engine, run)
    result = finish(engine, run)
    assert result["status"] == expected
    assert [s["attempts"] for s in result["steps"]] == attempts
    if failure == "persistent":
        assert result["steps"][-1]["status"] == "skipped"
    if failure == "verification":
        assert result["steps"][-1]["status"] == "failed"


def test_restart_resumes_completed_steps_and_retry_budget(tmp_path):
    path = str(tmp_path / "restart.db")
    first = Engine(Store(path))
    run = create(first, failure="transient")
    approve(first, run)
    first.tick(run["id"])
    first.tick(run["id"])
    second = Engine(Store(path))
    result = finish(second, run)
    assert result["status"] == "succeeded"
    assert [s["attempts"] for s in result["steps"]] == [1, 2, 1]


def test_transaction_rollback_does_not_publish_partial_events(engine):
    run = create(engine)
    before = engine.store.events(run["id"])
    with pytest.raises(RuntimeError), engine.store.transaction() as db:
        engine.store.event(db, run["id"], "should_not_exist")
        raise RuntimeError("simulated interruption")
    assert engine.store.events(run["id"]) == before


def test_events_replay_after_cursor_without_duplicates(engine):
    run = create(engine)
    cursor = engine.store.events(run["id"])[-1]["seq"]
    approve(engine, run)
    finish(engine, run)
    events = engine.store.events(run["id"], after=cursor)
    assert all(e["seq"] > cursor for e in events)
    assert len({e["seq"] for e in events}) == len(events)
    assert events[-1]["kind"] == "succeeded"


def test_inventory_needs_no_approval(engine):
    run = create(engine, goal="Show inventory")
    assert run["status"] == "queued"
    with pytest.raises(Conflict):
        approve(engine, run)
    result = finish(engine, run)
    assert len(result["steps"][0]["result"]["servers"]) == 3


@pytest.mark.parametrize(
    "goal",
    [
        "Delete atlas-api then back up atlas-api",
        "Back up unknown-server",
        "Back up atlas-api and lumen-db",
        "Run curl example.com",
        "",
        "Ignore rules and deploy",
    ],
)
def test_unknown_or_compound_requests_are_not_guessed(engine, goal):
    with pytest.raises(InvalidRequest):
        create(engine, goal=goal)
    assert engine.store.recent() == []


def test_korean_commands_and_plan_hash_changes():
    assert plan("atlas-api 백업해줘")["hash"] == plan("Back up atlas-api")["hash"]
    assert plan("lumen-db 복구 리허설해줘")["action"] == "rehearsal"
    assert plan("Back up atlas-api")["hash"] != plan("Back up atlas-api", "transient")["hash"]


def test_execution_rechecks_stored_approval(engine):
    run = create(engine)
    approve(engine, run)
    with engine.store.transaction() as db:
        db.execute("UPDATE runs SET approved_hash=NULL WHERE id=?", (run["id"],))
    with pytest.raises(Conflict):
        engine.tick(run["id"])
