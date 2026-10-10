from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_windows_unified_license_gaps import distribution_delta  # noqa: E402


def inventories() -> tuple[dict, dict]:
    old_rows = [{"name": f"base-{i}", "version": "1.0"} for i in range(93)]
    new_rows = [dict(row) for row in old_rows]
    new_rows += [{"name": f"extra-{i}", "version": "1.0"} for i in range(13)]
    return ({"distribution_count": 93, "distributions": old_rows},
            {"distribution_count": 106, "distributions": new_rows})


class LicenseGapAuditTests(unittest.TestCase):
    def test_exact_delta(self) -> None:
        old, new = inventories()
        self.assertEqual(len(distribution_delta(old, new)), 13)

    def test_changed_base_version_rejected(self) -> None:
        old, new = inventories()
        new["distributions"][0]["version"] = "2.0"
        with self.assertRaisesRegex(ValueError, "original 93"):
            distribution_delta(old, new)

    def test_duplicate_identity_rejected(self) -> None:
        old, new = inventories()
        new["distributions"][-1]["name"] = "BASE_0"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            distribution_delta(old, new)

    def test_wrong_distribution_count_rejected(self) -> None:
        old, new = inventories()
        new["distribution_count"] = 105
        with self.assertRaisesRegex(ValueError, "counts differ"):
            distribution_delta(old, new)


if __name__ == "__main__":
    unittest.main()
