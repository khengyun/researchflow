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


if __name__ == "__main__":
    unittest.main()
