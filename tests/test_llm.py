import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from ops_workflow_lab.engine import Engine
from ops_workflow_lab.llm import Intent, OllamaPlanner, validate_intent
from ops_workflow_lab.planner import InvalidRequest, PlannerUnavailable
from ops_workflow_lab.server import create_app
from ops_workflow_lab.store import Store


def mock_planner(content=None, **response_fields):
    intent = content or {"disposition": "accept", "action": "backup", "target": "atlas-api"}

    def respond(request):
        body = json.loads(request.content)
        assert body["format"]["additionalProperties"] is False
        assert body["think"] is False
        assert body["stream"] is False
        assert "tools" not in body
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": json.dumps(intent)},
                **response_fields,
            },
        )

    return OllamaPlanner("test-model", transport=httpx.MockTransport(respond))


def test_model_interpretation_keeps_server_owned_steps_and_approval(tmp_path):
    engine = Engine(Store(str(tmp_path / "test.db")), planner=mock_planner())
    run = engine.create("atlas-api 서버를 백업해 두고 싶어.", "transient", "llm-request-001")
    assert run["status"] == "awaiting_approval"
    assert run["plan"]["interpretation"]["model"] == "test-model"
    assert [s["tool"] for s in run["steps"]] == ["inspect", "snapshot", "verify"]
    assert engine.tick(run["id"])["steps"][0]["attempts"] == 0
    engine.decide(run["id"], run["plan"]["hash"], "approve")
    for _ in range(4):
        result = engine.tick(run["id"])
    assert result["status"] == "succeeded"
    assert result["steps"][1]["attempts"] == 2


@pytest.mark.parametrize(
    "intent,goal",
    [
        ({"disposition": "accept", "action": "backup", "target": "lumen-db"}, "Back up atlas-api"),
        (
            {"disposition": "accept", "action": "backup", "target": "atlas-api"},
            "Back up both atlas-api and lumen-db",
        ),
        (
            {"disposition": "accept", "action": "backup", "target": "lumen-db"},
            "Back up the database",
        ),
        ({"disposition": "accept", "action": "inventory", "target": "all"}, "Inspect atlas-api"),
        ({"disposition": "reject", "action": "none", "target": "none"}, "Delete atlas-api"),
        ({"disposition": "clarify", "action": "none", "target": "none"}, "Back up my server"),
    ],
)
def test_rejects_ungrounded_or_unsupported_intent(intent, goal):
    with pytest.raises(InvalidRequest):
        validate_intent(Intent.model_validate(intent), goal, "none")


@pytest.mark.parametrize(
    "content",
    [
        {"disposition": "accept", "action": "shell", "target": "atlas-api"},
        {"disposition": "accept", "action": "backup", "target": "atlas-api", "approved": True},
        {"disposition": "accept", "action": "backup", "target": "real-server"},
    ],
)
def test_extra_fields_and_unknown_capabilities_are_invalid(content):
    with pytest.raises(PlannerUnavailable):
        mock_planner(content)("Back up atlas-api")


def test_incomplete_and_non_json_responses_are_not_repaired():
    with pytest.raises(PlannerUnavailable):
        mock_planner(done=False)("Back up atlas-api")
    with pytest.raises(PlannerUnavailable):
        mock_planner(done_reason="length")("Back up atlas-api")
    planner = OllamaPlanner(
        "test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"done": True, "message": {"content": "not json"}}
            )
        ),
    )
    with pytest.raises(PlannerUnavailable):
        planner("Back up atlas-api")


@pytest.mark.parametrize(
    "url", ["https://remote.example", "http://127.0.0.1:11434/path", "http://localhost:11434?x=y"]
)
def test_only_loopback_inference_is_accepted(url):
    with pytest.raises(ValueError):
        OllamaPlanner("test", url)


def test_idempotent_replay_does_not_call_model_twice(tmp_path):
    calls = []
    planner = mock_planner()

    def count(goal, failure):
        calls.append(goal)
        return planner(goal, failure)

    engine = Engine(Store(str(tmp_path / "test.db")), planner=count)
    first = engine.create("Back up atlas-api", "none", "model-retry-01")
    assert engine.create("Back up atlas-api", "none", "model-retry-01")["id"] == first["id"]
    assert len(calls) == 1


def test_model_timeout_returns_503_without_creating_run(tmp_path):
    def timeout(request):
        raise httpx.ReadTimeout("untrusted private error detail")

    planner = OllamaPlanner("test", transport=httpx.MockTransport(timeout))
    with TestClient(create_app(str(tmp_path / "test.db"), planner=planner)) as client:
        result = client.post(
            "/api/runs",
            json={"goal": "Back up atlas-api"},
            headers={
                "Idempotency-Key": "timeout-request",
            },
        )
        assert result.status_code == 503
        assert "untrusted private" not in result.text
        assert client.get("/api/runs").json() == []
        assert client.get("/api/health").json()["planner"] == "ollama"


def test_model_call_does_not_lock_database_and_concurrent_inference_fails_fast(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def respond(request):
        entered.set()
        assert release.wait(timeout=5)
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {
                    "content": json.dumps(
                        {
                            "disposition": "accept",
                            "action": "backup",
                            "target": "atlas-api",
                        }
                    )
                },
            },
        )

    planner = OllamaPlanner("test", transport=httpx.MockTransport(respond))
    store = Store(str(tmp_path / "test.db"))
    engine = Engine(store, planner=planner)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(engine.create, "Back up atlas-api", "none", "concurrent-001")
        try:
            assert entered.wait(timeout=3)
            with store.transaction() as db:
                assert db.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0
            with pytest.raises(PlannerUnavailable, match="busy"):
                engine.create("Back up atlas-api", "none", "concurrent-002")
        finally:
            release.set()
        assert future.result(timeout=3)["status"] == "awaiting_approval"
