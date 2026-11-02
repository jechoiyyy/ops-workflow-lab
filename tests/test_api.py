import json
import time

from fastapi.testclient import TestClient

from ops_workflow_lab.server import create_app


def post_run(client, goal="Back up atlas-api", key="http-request-01"):
    return client.post("/api/runs", json={"goal": goal}, headers={"Idempotency-Key": key})


def wait_terminal(client, run_id):
    for _ in range(200):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] in {"succeeded", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError("Worker did not finish the run.")


def test_full_http_flow_and_sse_replay(tmp_path):
    app = create_app(str(tmp_path / "api.db"), tick_interval=0.01)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        response = post_run(client)
        assert response.status_code == 201
        run = response.json()
        assert (
            client.post(
                f"/api/runs/{run['id']}/decision",
                json={
                    "plan_hash": "0" * 64,
                    "decision": "approve",
                },
            ).status_code
            == 409
        )
        approved = client.post(
            f"/api/runs/{run['id']}/decision",
            json={
                "plan_hash": run["plan"]["hash"],
                "decision": "approve",
            },
        )
        assert approved.status_code == 200
        assert wait_terminal(client, run["id"])["status"] == "succeeded"
        all_events = client.get(f"/api/runs/{run['id']}/events").json()
        cursor = all_events[2]["seq"]
        response = client.get(
            f"/api/runs/{run['id']}/stream", headers={"Last-Event-ID": str(cursor)}
        )
        assert response.headers["content-type"].startswith("text/event-stream")
        ids = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
        assert ids == [event["seq"] for event in all_events if event["seq"] > cursor]
        assert "event: done" in response.text
        payloads = [
            json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        assert payloads[-1]["status"] == "succeeded"


def test_http_validation_and_local_boundary(tmp_path):
    with TestClient(create_app(str(tmp_path / "api.db"))) as client:
        assert client.get("/api/runs/missing").status_code == 404
        assert client.post("/api/runs", json={"goal": "Show inventory"}).status_code == 422
        assert post_run(client, key="short").status_code == 400
        assert post_run(client, goal="Delete all servers").status_code == 400
        assert (
            client.post(
                "/api/runs",
                json={"goal": "Show inventory", "approved": True},
                headers={"Idempotency-Key": "invalid-extra"},
            ).status_code
            == 422
        )
        assert client.get("/api/targets", headers={"Host": "untrusted.example"}).status_code == 400
        assert (
            client.post(
                "/api/runs",
                json={"goal": "Show inventory"},
                headers={
                    "Origin": "https://untrusted.example",
                    "Idempotency-Key": "cross-site-request",
                },
            ).status_code
            == 403
        )
        assert (
            client.get("/api/targets", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        )
        assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]
        run = post_run(client).json()
        assert (
            client.get(
                f"/api/runs/{run['id']}/stream",
                headers={
                    "Last-Event-ID": "invalid",
                },
            ).status_code
            == 400
        )


def test_new_worker_resumes_previously_queued_run(tmp_path):
    path = str(tmp_path / "resume.db")
    first = create_app(path)
    engine = first.state.engine
    run = engine.create("Rehearse recovery for lumen-db", "none", "restart-request")
    engine.decide(run["id"], run["plan"]["hash"], "approve")
    engine.tick(run["id"])
    with TestClient(create_app(path, tick_interval=0.01)) as client:
        result = wait_terminal(client, run["id"])
        assert result["status"] == "succeeded"
        assert [s["attempts"] for s in result["steps"]] == [1, 1, 1]
