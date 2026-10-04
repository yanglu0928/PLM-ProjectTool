from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "validation/api-05-contract-lint/contract_lint.py"
SPEC = importlib.util.spec_from_file_location("api05_contract_lint", MODULE_PATH)
assert SPEC and SPEC.loader
contract_lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract_lint
SPEC.loader.exec_module(contract_lint)


class ContractLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = contract_lint.read_sources(ROOT)
        cls.operations = contract_lint.parse_operations(cls.sources)

    def test_full_candidate_validation(self) -> None:
        result = contract_lint.validate(ROOT)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(22, result["owner_count"])
        self.assertEqual(65, result["root_count"])
        self.assertEqual(323, result["operation_count"])
        self.assertEqual(150, result["error_code_count"])
        self.assertEqual(18, result["sse_event_count"])
        self.assertEqual(20, result["query_mapping_count"])

    def test_operation_ids_and_paths_are_unique(self) -> None:
        operation_ids = [item.operation_id for item in self.operations]
        method_paths = [
            (item.method, path)
            for item in self.operations
            for path in item.expanded_paths
        ]
        self.assertEqual(len(operation_ids), len(set(operation_ids)))
        self.assertEqual(len(method_paths), len(set(method_paths)))

    def test_write_controls_are_fail_closed(self) -> None:
        for item in self.operations:
            if item.method in {"POST", "PATCH", "PUT"} and item.operation_id != "AUTH_LOGIN":
                self.assertIn("C", item.controls, item.operation_id)
            if item.method == "PATCH":
                self.assertIn("M", item.controls, item.operation_id)
            if item.method == "GET":
                self.assertNotIn("C", item.controls, item.operation_id)

    def test_root_catalog_matches_schema_manifest(self) -> None:
        roots = contract_lint.parse_root_exposure(self.sources[contract_lint.SOURCE_DOCS[0]])
        api_root_ids = {item.root_id for item in roots}
        self.assertEqual(contract_lint.parse_schema_root_ids(ROOT), api_root_ids)
        self.assertEqual(65, len(api_root_ids))

    def test_query_map_and_enums_are_closed(self) -> None:
        self.assertEqual(contract_lint.parse_schema_query_ids(ROOT), set(contract_lint.QUERY_OPERATION_MAP))
        for values in contract_lint.ENUM_CATALOG.values():
            self.assertEqual(len(values), len(set(values)))


if __name__ == "__main__":
    unittest.main()
