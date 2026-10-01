from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_windows_unified_pg18_candidate import KIND, PLAN_SHA256  # noqa: E402
from plan_windows_unified_pg18_install import plan_install  # noqa: E402


class UnifiedPg18InstallPlanTests(unittest.TestCase):
    def test_unsafe_root_rejected_before_zip_read(self) -> None:
        with patch("plan_windows_unified_pg18_install.inspect") as inspect:
            with self.assertRaisesRegex(ValueError, "ASCII"):
                plan_install(Path("missing.zip"), "D:\\中文\\PLM")
            inspect.assert_not_called()

    def test_missing_legal_gate_flag_rejected(self) -> None:
        manifest = {
            "kind": KIND, "installation_performed": False, "database_started_by_assembly": False,
            "legal_clearance": True, "corresponding_source_included": False,
            "source_plan_sha256": PLAN_SHA256, "postgresql_version": "18.6",
            "pgvector_version": "0.8.6", "vendored_python_distributions": 106,
            "no_jbig_pe_count": 34, "ocr_python_notice_file_count": 25,
        }
        with patch("plan_windows_unified_pg18_install.inspect", return_value=(manifest, {})):
            with self.assertRaisesRegex(ValueError, "gate metadata"):
                plan_install(Path("fixture.zip"), "C:\\PLMTool")


if __name__ == "__main__":
    unittest.main()
