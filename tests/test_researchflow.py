from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from researchflow.compare import compare_experiments
from researchflow.lineage import build_graph, trace, validate_graph
from researchflow.scan import scan_runs
from researchflow.search import search_experiments
from researchflow.store import init_project, load_experiments
from researchflow.vector_search import build_vector_index, vector_search_experiments


class FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def get(self, include=None) -> dict:
        return {"ids": list(self.rows)}

    def delete(self, ids: list[str]) -> None:
        for exp_id in ids:
            self.rows.pop(exp_id, None)

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        for exp_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            self.rows[exp_id] = {"document": document, "metadata": metadata, "embedding": embedding}

    def count(self) -> int:
        return len(self.rows)

    def query(self, query_embeddings: list[list[float]], n_results: int, include: list[str]) -> dict:
        query = query_embeddings[0]
        ranked = sorted(
            self.rows.items(),
            key=lambda item: abs(item[1]["embedding"][0] - query[0]),
        )[:n_results]
        return {
            "ids": [[exp_id for exp_id, _ in ranked]],
            "documents": [[row["document"] for _, row in ranked]],
            "metadatas": [[row["metadata"] for _, row in ranked]],
            "distances": [[abs(row["embedding"][0] - query[0]) for _, row in ranked]],
        }


class FakeClient:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def get_or_create_collection(self, name: str, metadata: dict | None = None) -> FakeCollection:
        return self.collection

    def delete_collection(self, name: str) -> None:
        self.collection = FakeCollection()


class FakeModel:
    def encode_document(self, documents: list[str], **kwargs) -> list[list[float]]:
        return [[1.0 if "Version: 0.2.0" in document else 0.0] for document in documents]

    def encode_query(self, queries: list[str], **kwargs) -> list[list[float]]:
        return [[1.0 if "derived" in query.lower() else 0.0] for query in queries]


class ResearchFlowTest(unittest.TestCase):
    def copy_fixture(self, tmp_path: Path) -> Path:
        source = Path(__file__).resolve().parents[1] / "examples" / "fixture_project"
        dest = tmp_path / "fixture"
        ignore = shutil.ignore_patterns(".researchflow", "__pycache__")
        shutil.copytree(source, dest, ignore=ignore)
        return dest

    def test_scan_search_trace_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_fixture(Path(tmp))
            init_project(root)
            scan = scan_runs(root, run_roots=["runs"])
            self.assertEqual(scan["created"], 2)

            experiments = load_experiments(root)
            self.assertEqual(len(experiments), 2)
            self.assertEqual({item["version"] for item in experiments}, {"0.1.0", "0.2.0"})

            results = search_experiments(root, "derived 0.2.0")
            self.assertTrue(results)
            self.assertEqual(results[0]["version"], "0.2.0")

            graph = build_graph(root, write=True)
            self.assertEqual(len(graph["nodes"]), 2)
            self.assertEqual(len(graph["edges"]), 1)

            derived_id = next(item["id"] for item in experiments if item["version"] == "0.2.0")
            traced = trace(root, derived_id)
            self.assertTrue(traced["ancestors"])

            compared = compare_experiments(root, "0.1.0", "0.2.0")
            self.assertEqual(compared["metric_delta"]["val_mae"]["delta"], -2.0)

            validation = validate_graph(root)
            self.assertTrue(validation["ok"], validation["errors"])

            graph_json = json.loads((root / ".researchflow" / "indexes" / "graph.json").read_text())
            self.assertTrue(graph_json["nodes"])

    def test_vector_index_uses_experiment_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.copy_fixture(Path(tmp))
            init_project(root)
            scan_runs(root, run_roots=["runs"])
            client = FakeClient()
            model = FakeModel()

            indexed = build_vector_index(root, client=client, model=model)
            self.assertTrue(indexed["ok"])
            self.assertEqual(indexed["documents"], 2)

            results = vector_search_experiments(root, "derived run", client=client, model=model)
            self.assertTrue(results)
            self.assertEqual(results[0]["version"], "0.2.0")


if __name__ == "__main__":
    unittest.main()
