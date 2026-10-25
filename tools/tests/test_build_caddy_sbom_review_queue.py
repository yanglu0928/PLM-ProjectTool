from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_caddy_sbom_review_queue import rows_from_sbom, serialize_csv  # noqa: E402


class CaddySbomQueueTests(unittest.TestCase):
    def fixture(self) -> dict:
        return {"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [
            {"bom-ref": f"ref-{i:03}", "name": f"component-{i}", "version": "1"}
            for i in range(149)]}

    def test_missing_license_is_unknown_not_approval(self) -> None:
        source = self.fixture()
        source["components"][0]["licenses"] = [{"license": {"id": "Apache-2.0"}}]
        rows = rows_from_sbom(source)
        self.assertEqual(rows[0]["sbom_license"], "Apache-2.0")
        self.assertEqual(rows[1]["sbom_license"], "UNDECLARED_IN_SBOM")
        self.assertTrue(all(row["review_status"] == "REVIEW_REQUIRED" for row in rows))
        self.assertEqual(serialize_csv(rows).count(b"\n"), 150)

    def test_duplicate_reference_rejected(self) -> None:
        source = self.fixture()
        source["components"][1]["bom-ref"] = source["components"][0]["bom-ref"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            rows_from_sbom(source)


if __name__ == "__main__":
    unittest.main()
