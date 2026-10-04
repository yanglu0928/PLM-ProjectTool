from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_postgresql18_pgvector_windows_inputs import _hash_stream, verify_assets  # noqa: E402


class PgOfflineInputAuditTests(unittest.TestCase):
    def test_exact_asset_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg-input-unit-") as temp:
            root = Path(temp)
            path = root / "synthetic.zip"
            path.write_bytes(b"offline")
            expected = {"synthetic.zip": (7, hashlib.sha256(b"offline").hexdigest())}
            with patch("audit_postgresql18_pgvector_windows_inputs.ASSETS", expected):
                self.assertEqual(len(verify_assets(root)), 1)

    def test_mutated_or_missing_asset_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-pg-input-unit-") as temp:
            root = Path(temp)
            path = root / "synthetic.zip"
            expected = {"synthetic.zip": (7, hashlib.sha256(b"offline").hexdigest())}
            with patch("audit_postgresql18_pgvector_windows_inputs.ASSETS", expected):
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    verify_assets(root)
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "identity mismatch"):
                    verify_assets(root)

    def test_stream_hash_matches_bytes(self) -> None:
        self.assertEqual(_hash_stream(io.BytesIO(b"abc")), hashlib.sha256(b"abc").hexdigest())


if __name__ == "__main__":
    unittest.main()
