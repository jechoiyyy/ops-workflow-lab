"""Versioned synthetic corpus with metadata filtering and local dense retrieval."""

import json
import math
import threading
from pathlib import Path

import httpx

from .planner import InvalidRequest, PlannerUnavailable, digest

CORPUS_PATH = Path(__file__).parent / "data" / "runbooks.json"


class RunbookRetriever:
    def __init__(self, model="bge-m3:latest", base_url="http://127.0.0.1:11434", embed=None):
        self.model = model
        self.base_url = base_url
        self.corpus = json.loads(CORPUS_PATH.read_text())
        self.corpus_hash = digest(self.corpus)
        self.documents = self.corpus["documents"]
        self.embed = embed or self._ollama_embed
        self._vectors = None
        self._lock = threading.Lock()

    def _ollama_embed(self, texts):
        try:
            with httpx.Client(timeout=120, trust_env=False, follow_redirects=False) as client:
                response = client.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": texts,
                        "truncate": False,
                    },
                )
                response.raise_for_status()
                return response.json()["embeddings"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise PlannerUnavailable(
                "Local embedding model failed. No fallback or plan was created."
            ) from exc

    @staticmethod
    def _normalize(vectors, expected):
        if not isinstance(vectors, list) or len(vectors) != expected:
            raise PlannerUnavailable("Embedding response has the wrong number of vectors.")
        normalized = []
        for vector in vectors:
            if (
                not isinstance(vector, list)
                or not vector
                or not all(
                    isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in vector
                )
            ):
                raise PlannerUnavailable("Embedding response contains an invalid vector.")
            norm = math.sqrt(sum(v * v for v in vector))
            if not norm or not math.isfinite(norm):
                raise PlannerUnavailable("Embedding response contains a zero or invalid vector.")
            normalized.append([v / norm for v in vector])
        if len({len(v) for v in normalized}) != 1:
            raise PlannerUnavailable("Embedding dimensions are inconsistent.")
        return normalized

    def search(self, query: str, action: str, role: str, top_k: int = 3) -> list[dict]:
        with self._lock:
            if self._vectors is None:
                texts = [f"{d['title']}\n{d['text']}" for d in self.documents]
                self._vectors = self._normalize(self.embed(texts), len(texts))
        vector = self._normalize(self.embed([query]), 1)[0]
        if len(vector) != len(self._vectors[0]):
            raise PlannerUnavailable("Query and document embedding dimensions differ.")
        hits = []
        for document, embedding in zip(self.documents, self._vectors, strict=True):
            # Applicability and lifecycle constraints precede semantic ranking.
            if (
                document["status"] != "active"
                or document["action"] != action
                or role not in document["roles"]
            ):
                continue
            hits.append(
                {
                    **document,
                    "score": round(sum(a * b for a, b in zip(vector, embedding, strict=True)), 6),
                }
            )
        hits.sort(key=lambda hit: (-hit["score"], hit["id"]))
        return hits[:top_k]

    def required(self, action, role):
        return {
            d["id"]
            for d in self.documents
            if d["status"] == "active"
            and d["required"]
            and d["action"] == action
            and role in d["roles"]
        }

    def ensure_coverage(self, evidence, action, role):
        required = self.required(action, role)
        if not required or not required <= {d["id"] for d in evidence}:
            raise InvalidRequest(
                "Required applicable runbook evidence is missing; planning stopped."
            )
