"""Loopback-only local UI and API. The application is a single-user demo."""

import argparse
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import TERMINAL, Engine
from .grounded import GroundedPlanner
from .llm import OllamaPlanner
from .planner import TARGETS, Conflict, InvalidRequest, NotFound, PlannerUnavailable
from .store import Store

ASSETS = Path(__file__).parent / "static"
logger = logging.getLogger(__name__)


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: str = Field(min_length=1, max_length=180)
    failure: str = "none"


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_hash: str = Field(min_length=64, max_length=64)
    decision: str


def create_app(
    db_path: str | None = None,
    tick_interval: float = 0.65,
    planner: OllamaPlanner | GroundedPlanner | None = None,
) -> FastAPI:
    store = Store(db_path or os.environ.get("OPS_LAB_DB", ".data/lab.db"))
    engine = Engine(store, planner=planner) if planner else Engine(store)

    async def work():
        while True:
            for run_id in await asyncio.to_thread(store.ready):
                try:
                    await asyncio.to_thread(engine.tick, run_id)
                except Exception:
                    logger.exception("Workflow tick failed for run %s", run_id)
            await asyncio.sleep(tick_interval)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(work())
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(
        title="Ops Workflow Lab",
        version="0.2.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.store = store
    app.state.engine = engine
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin and origin != expected:
            return JSONResponse({"detail": "Cross-origin requests are disabled."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are disabled."}, status_code=403)
        if request.method == "POST":
            try:
                size = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            if size > 4096:
                return JSONResponse({"detail": "Request is too large."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    async def domain_error(request, exc):
        status = 404 if isinstance(exc, NotFound) else 409 if isinstance(exc, Conflict) else 400
        if isinstance(exc, PlannerUnavailable):
            status = 503
        return JSONResponse({"detail": str(exc)}, status_code=status)

    for error in (InvalidRequest, Conflict, NotFound, PlannerUnavailable):
        app.add_exception_handler(error, domain_error)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "mode": "synthetic",
            "planner": getattr(planner, "mode", "ollama") if planner else "deterministic",
            "model": planner.model if planner else None,
            "embedding_model": getattr(planner, "embedding_model", None),
        }

    @app.get("/api/targets")
    def targets():
        return TARGETS

    @app.get("/api/runs")
    def runs():
        return store.recent()

    @app.post("/api/runs", status_code=201)
    def create(body: RunInput, idempotency_key: str = Header(alias="Idempotency-Key")):
        return engine.create(body.goal, body.failure, idempotency_key)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return store.get(run_id)

    @app.post("/api/runs/{run_id}/decision")
    def decide(run_id: str, body: DecisionInput):
        return engine.decide(run_id, body.plan_hash, body.decision)

    @app.get("/api/runs/{run_id}/events")
    def event_list(run_id: str, after: int = 0):
        return store.events(run_id, max(0, after))

    @app.get("/api/runs/{run_id}/stream")
    async def stream(run_id: str, request: Request, after: int = 0):
        await asyncio.to_thread(store.get, run_id)
        try:
            cursor = max(0, after, int(request.headers.get("last-event-id", "0")))
        except ValueError as exc:
            raise InvalidRequest("Last-Event-ID must be an integer.") from exc

        async def generate():
            nonlocal cursor
            yield ": connected\n\n"
            while not await request.is_disconnected():
                batch = await asyncio.to_thread(store.events, run_id, cursor)
                for event in batch:
                    cursor = event["seq"]
                    yield f"id: {cursor}\nevent: trace\ndata: {json.dumps(event)}\n\n"
                run = await asyncio.to_thread(store.get, run_id)
                if run["status"] in TERMINAL:
                    # A tick may have committed after the first read; drain that tail.
                    for event in await asyncio.to_thread(store.events, run_id, cursor):
                        cursor = event["seq"]
                        yield f"id: {cursor}\nevent: trace\ndata: {json.dumps(event)}\n\n"
                    yield f"event: done\ndata: {json.dumps(run)}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ASSETS / "index.html")

    @app.get("/docs", include_in_schema=False)
    def api_reference():
        return FileResponse(ASSETS / "api.html")

    app.mount("/static", StaticFiles(directory=ASSETS), name="static")
    return app


def main():
    parser = argparse.ArgumentParser(description="Run the local synthetic operations lab.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=os.environ.get("OPS_LAB_DB", ".data/lab.db"))
    parser.add_argument(
        "--planner", choices=["deterministic", "ollama", "rag"], default="deterministic"
    )
    parser.add_argument("--embedding-model", default="bge-m3:latest")
    parser.add_argument("--model", default=os.environ.get("OPS_LAB_MODEL", ""))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.planner != "deterministic" and not args.model:
        parser.error(
            "--model is required with --planner ollama; use an installed local model name."
        )
    planner = OllamaPlanner(args.model, args.ollama_url) if args.planner == "ollama" else None
    if args.planner == "rag":
        planner = GroundedPlanner(args.model, args.ollama_url, args.embedding_model)
    uvicorn.run(
        create_app(args.db, planner=planner), host="127.0.0.1", port=args.port, access_log=False
    )


if __name__ == "__main__":
    main()
