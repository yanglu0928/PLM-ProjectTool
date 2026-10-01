from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_windows_pg18_sidecar import check_stage  # noqa: E402


class PgSidecarSmokeTests(unittest.TestCase):
    def test_non_temp_root_rejected_before_verification(self) -> None:
        with patch("smoke_windows_pg18_sidecar.verify") as verify:
            with self.assertRaisesRegex(ValueError, "isolated Temp child"):
                check_stage(Path(__file__).resolve().parents[2])
            verify.assert_not_called()

    def test_missing_runtime_executable_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg18-stage-unit-") as temp:
            root = Path(temp)
            (root / "payload" / "pgsql" / "bin").mkdir(parents=True)
            with patch("smoke_windows_pg18_sidecar.verify") as verify:
                with self.assertRaisesRegex(ValueError, "executable missing"):
                    check_stage(root)
                verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
