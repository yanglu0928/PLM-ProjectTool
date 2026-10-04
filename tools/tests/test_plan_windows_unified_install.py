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
from plan_windows_unified_install import digest_archive, inspect_candidate, plan  # noqa: E402


def synthetic_archive(path: Path, payload: bytes = b"synthetic", release: bool = False) -> None:
    digest = hashlib.sha256(b"synthetic").hexdigest()
    with zipfile.ZipFile(path, "w") as output:
        output.writestr("payload/runtime/python.exe", payload)
        output.writestr("payload-sha256sums.txt", f"{digest}  payload/runtime/python.exe\n")
        output.writestr("manifest.json", json.dumps({
            "kind": "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE", "release_eligible": release,
            "vendored_python_distributions": 106, "no_jbig_pe_count": 34,
            "old_tesseract_included": False, "payload_file_count": 1,
        }))
        output.writestr("third-party-inventory.json", json.dumps({
            "distribution_count": 106, "status": "REVIEW_REQUIRED",
        }))


class InstallPlanTests(unittest.TestCase):
    def test_synthetic_candidate_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "candidate.zip"
            synthetic_archive(archive)
            result = inspect_candidate(archive, expected_sha256=digest_archive(archive))
            self.assertEqual(result["payload_file_count"], 1)

    def test_payload_tamper_and_release_claim_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "candidate.zip"
            synthetic_archive(archive, payload=b"tampered")
            with self.assertRaisesRegex(ValueError, "payload hash mismatch"):
                inspect_candidate(archive, expected_sha256=digest_archive(archive))
            synthetic_archive(archive, release=True)
            with self.assertRaisesRegex(ValueError, "metadata contradicts"):
                inspect_candidate(archive, expected_sha256=digest_archive(archive))

    def test_unknown_archive_identity_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "candidate.zip"
            synthetic_archive(archive)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                inspect_candidate(archive)

    def test_unsafe_root_rejected_before_archive_io(self) -> None:
        with patch("plan_windows_unified_install.inspect_candidate") as inspect:
            with self.assertRaisesRegex(ValueError, "ASCII"):
                plan(Path("does-not-exist.zip"), "D:\\AI工具\\PLMTool")
            inspect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
