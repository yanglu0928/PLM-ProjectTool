from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_packaged_pg18_migration import HEAD, verify_layout  # noqa: E402


class PackagedMigrationSmokeTests(unittest.TestCase):
    def test_head_is_pinned(self) -> None:
        self.assertEqual(HEAD, "20260930_0051")

    def test_repository_path_is_not_an_install_rehearsal(self) -> None:
        with patch("smoke_packaged_pg18_migration.inspect", return_value=({}, {})):
            with self.assertRaisesRegex(ValueError, "direct ASCII isolated"):
                verify_layout(Path(__file__).resolve().parents[2], Path("fixture.zip"))

    def test_missing_install_metadata_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-install-rehearsal-") as temp:
            with patch("smoke_packaged_pg18_migration.inspect", return_value=({}, {})):
                with self.assertRaises(FileNotFoundError):
                    verify_layout(Path(temp), Path("fixture.zip"))


if __name__ == "__main__":
    unittest.main()
