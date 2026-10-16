from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_current_app_packaged_migration import smoke  # noqa: E402


class PackagedMigrationBoundaryTests(unittest.TestCase):
    def test_rejects_non_stage_before_database_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.zip"
            candidate.write_bytes(b"synthetic")
            with self.assertRaisesRegex(ValueError, "identity rejected"):
                smoke(root, candidate, "0" * 64)


if __name__ == "__main__":
    unittest.main()
