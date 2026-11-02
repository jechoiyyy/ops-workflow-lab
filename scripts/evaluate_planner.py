"""Opt-in live evaluation on synthetic cases, not a general model benchmark."""

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ops_workflow_lab.llm import PROMPT_VERSION, SYSTEM_PROMPT, OllamaPlanner
from ops_workflow_lab.planner import InvalidRequest, PlannerUnavailable, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", default=".data/evaluation.json")
    parser.add_argument("--cases", default="evals/cases.json")
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text())
    planner = OllamaPlanner(args.model)
    # Refuse to run if the model is not already present; never download it implicitly.
    with httpx.Client(trust_env=False, timeout=5) as client:
        models = client.get(f"{planner.base_url}/api/tags").raise_for_status().json()["models"]
        installed = next((m for m in models if m["name"] == args.model), None)
        version = client.get(f"{planner.base_url}/api/version").raise_for_status().json()
    if installed is None:
        parser.error("Model not installed. Select a name from ollama list.")
    results = []
    for case in cases:
        started = time.perf_counter()
        observed, error, interpretation = None, None, None
        try:
            result = planner(case["goal"])
            observed = {"action": result["action"], "target": result["target"]}
            interpretation = result["interpretation"]
        except InvalidRequest:
            pass
        except PlannerUnavailable as exc:
            error = str(exc)
        row = {
            **case,
            "observed": observed,
            "matched": observed == case["expected"] and error is None,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "runtime_error": error,
            "interpretation": interpretation,
        }
        results.append(row)
        print(
            f"{case['id']}: {'PASS' if row['matched'] else 'FAIL'} ({row['latency_ms']} ms)",
            flush=True,
        )
    latencies = sorted(row["latency_ms"] for row in results)
    report = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "scope": (
            "Synthetic intent-planning pipeline smoke test; "
            "one sample per case, not a general benchmark."
        ),
        "model": args.model,
        "model_digest": installed["digest"],
        "ollama_version": version["version"],
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": digest(SYSTEM_PROMPT),
        "cases_sha256": digest(cases),
        "temperature": 0,
        "seed": 7,
        "num_predict": 160,
        "think": False,
        "total": len(results),
        "matched": sum(r["matched"] for r in results),
        "runtime_errors": sum(r["runtime_error"] is not None for r in results),
        "median_latency_ms": statistics.median(latencies),
        "max_latency_ms": max(latencies),
        "results": results,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Matched {report['matched']}/{report['total']}; report: {output}")
    return 0 if all(row["matched"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
