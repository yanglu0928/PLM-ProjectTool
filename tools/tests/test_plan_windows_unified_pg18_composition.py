from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_windows_unified_pg18_composition import inspect, plan  # noqa: E402


class WindowsPgCompositionPlanTests(unittest.TestCase):
    def test_byte_verified_synthetic_zip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg-composition-unit-") as temp:
            archive = Path(temp) / "fixture.zip"
            payload = b"synthetic"
            name = "payload/pgsql/bin/test.exe"
            digest = hashlib.sha256(payload).hexdigest()
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(name, payload)
                bundle.writestr("payload-sha256sums.txt", f"{digest}  {name}\n")
                bundle.writestr("manifest.json", json.dumps({"kind": "TEST", "release_eligible": False,
                                                               "payload_file_count": 1}))
                bundle.writestr("third-party-inventory.json", "{}")
            archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            _, files = inspect(archive, archive_hash, "TEST", 1)
            self.assertEqual(files, {name: digest})
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                inspect(archive, "0" * 64, "TEST", 1)

    def test_case_insensitive_collision_rejected(self) -> None:
        with patch("plan_windows_unified_pg18_composition.inspect", side_effect=[
            ({"kind": "UNIFIED"}, {"payload/pgsql/bin/pg_ctl.exe": "a" * 64}),
            ({"kind": "PG"}, {"payload/pgsql/bin/pg_ctl.exe": "a" * 64}),
        ]):
            with self.assertRaisesRegex(ValueError, "path conflict"):
                plan(Path("a"), Path("b"))


if __name__ == "__main__":
    unittest.main()
