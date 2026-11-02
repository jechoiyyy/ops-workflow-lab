"""Opt-in local RAG smoke evaluation. Inputs and provider effects are synthetic."""

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ops_workflow_lab.engine import TERMINAL, Engine
from ops_workflow_lab.grounded import GroundedPlanner, check_policy
from ops_workflow_lab.planner import TARGETS, InvalidRequest, PlannerUnavailable
from ops_workflow_lab.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--embedding-model", default="bge-m3:latest")
    parser.add_argument("--output", default="docs/evaluation-grounded.json")
    args = parser.parse_args()
    planner = GroundedPlanner(args.model, embedding_model=args.embedding_model)
    cases = json.loads(Path("evals/grounded.json").read_text())
    results = []
    with tempfile.TemporaryDirectory() as directory:
        engine = Engine(Store(str(Path(directory) / "eval.db")), planner=planner)
        for case in cases:
            result = {"id": case["id"], "passed": False}
            try:
                run = engine.create(case["goal"], case.get("failure", "none"), "eval-" + case["id"])
                proposal = run["plan"]
                intent = proposal["interpretation"]["intent"]
                result.update(intent=intent, latency_ms=proposal["interpretation"]["latency_ms"])
                policies = proposal.get("policies", [])
                citations_valid = True
                required_recall = []
                lookup = {d["id"]: d for d in planner.retriever.documents}
                for policy in policies:
                    evidence = [lookup[d["id"]] for d in policy["evidence"]]
                    citations_valid &= not check_policy({"controls": policy["controls"]}, evidence)
                    role = next(t["role"] for t in TARGETS if t["id"] == policy["target"])
                    required = planner.retriever.required(proposal["action"], role)
                    required_recall.append(
                        len(required & {d["id"] for d in evidence}) / len(required)
                    )
                if proposal["requires_approval"]:
                    engine.decide(run["id"], proposal["hash"], "approve")
                for _ in range(30):
                    run = engine.tick(run["id"])
                    if run["status"] in TERMINAL:
                        break
                result.update(
                    status=run["status"],
                    citations_valid=citations_valid,
                    required_document_recall_at_3=required_recall,
                    generation_attempts=[p["attempts"] for p in policies],
                    retrieved_ids=[[d["id"] for d in p["evidence"]] for p in policies],
                )
                result["passed"] = (
                    not case.get("reject")
                    and intent["action"] == case["action"]
                    and intent["targets"] == case["targets"]
                    and citations_valid
                    and all(v == 1 for v in required_recall)
                    and run["status"] == case["status"]
                )
            except (InvalidRequest, PlannerUnavailable) as exc:
                result.update(error=type(exc).__name__, message=str(exc))
                result["passed"] = bool(case.get("reject") and isinstance(exc, InvalidRequest))
            results.append(result)
            print(f"{case['id']}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "model": args.model,
        "embedding_model": args.embedding_model,
        "prompt_version": "grounded-v1",
        "corpus_hash": planner.retriever.corpus_hash,
        "scope": (
            "Small development smoke set, not a holdout or production benchmark. "
            "Metadata-filtered corpus has only 1–2 eligible documents per target, "
            "so recall@3 does not measure ranking discrimination."
        ),
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "results": results,
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
