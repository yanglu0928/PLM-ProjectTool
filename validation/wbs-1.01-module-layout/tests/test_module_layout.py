from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "validate_module_layout.py"
SPEC = importlib.util.spec_from_file_location("module_layout_validator", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load module layout validator")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ModuleLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = VALIDATOR.validate()
        cls.manifest = VALIDATOR.load_json(VALIDATOR.MANIFEST_PATH)
        cls.api_manifest = VALIDATOR.load_json(VALIDATOR.API_MANIFEST_PATH)

    def test_full_validation_passes(self) -> None:
        self.assertEqual("PASS", self.result["status"])

    def test_runtime_modules_match_frozen_api_owners(self) -> None:
        names = {item["name"] for item in self.manifest["runtime_modules"]}
        owners = {item["owner"] for item in self.api_manifest["roots"]}
        self.assertEqual(22, len(names))
        self.assertEqual(65, len(self.api_manifest["roots"]))
        self.assertEqual(owners, names)

    def test_dependencies_match_frozen_architecture(self) -> None:
        graph = {
            item["name"]: item["allowed_dependencies"]
            for item in self.manifest["runtime_modules"]
        }
        frozen = VALIDATOR.parse_frozen_dependency_matrix(
            VALIDATOR.ARCHITECTURE_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(frozen, graph)
        self.assertEqual(0, self.result["dependency_cycle_count"])

    def test_layer_graph_is_closed_and_acyclic(self) -> None:
        graph = self.manifest["backend"]["layer_dependencies"]
        self.assertEqual(
            {"api", "application", "domain", "infrastructure"}, set(graph)
        )
        VALIDATOR.assert_acyclic(graph)

    def test_developer_workbench_is_not_customer_runtime(self) -> None:
        workbench = self.manifest["developer_workbench"]
        self.assertTrue(workbench["separate_trust_zone"])
        self.assertFalse(workbench["included_in_customer_runtime"])
        self.assertEqual([], workbench["allowed_runtime_dependencies"])

    def test_required_repository_entries_exist(self) -> None:
        self.assertEqual(0, self.result["missing_path_count"])
        self.assertEqual(8, self.result["required_path_count"])


if __name__ == "__main__":
    unittest.main()
