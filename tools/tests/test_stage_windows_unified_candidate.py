from __future__ import annotations

import sys
import hashlib
import json
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage_windows_unified_candidate import stage, validate_stage_root  # noqa: E402
from plan_windows_unified_install import digest_archive, inspect_candidate  # noqa: E402


def synthetic_archive(path: Path) -> None:
    content = b"synthetic"
    digest = hashlib.sha256(content).hexdigest()
    with zipfile.ZipFile(path, "w") as output:
        output.writestr("payload/runtime/python.exe", content)
        output.writestr("payload-sha256sums.txt", f"{digest}  payload/runtime/python.exe\n")
        output.writestr("manifest.json", json.dumps({
            "kind": "WINDOWS11_UNIFIED_DEVELOPMENT_CANDIDATE", "release_eligible": False,
            "vendored_python_distributions": 106, "no_jbig_pe_count": 34,
            "old_tesseract_included": False, "payload_file_count": 1,
        }))
        output.writestr("third-party-inventory.json", json.dumps({
            "distribution_count": 106, "status": "REVIEW_REQUIRED",
        }))


class StageCandidateTests(unittest.TestCase):
    def test_only_fresh_direct_ascii_temp_child_allowed(self) -> None:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        root = temp / ("plm-unified-stage-" + uuid.uuid4().hex)
        self.assertEqual(validate_stage_root(root), root)
        for unsafe in (Path("C:\\PLMTool"), temp / "plm-unified-stage-中文12345678",
                       temp / "subdir" / ("plm-unified-stage-" + uuid.uuid4().hex)):
            with self.subTest(unsafe=str(unsafe)), self.assertRaises((ValueError, OSError)):
                validate_stage_root(unsafe)
        with patch.object(Path, "exists", return_value=True):
            with self.assertRaisesRegex(ValueError, "must not exist"):
                validate_stage_root(root)

    def test_invalid_source_fails_before_creating_staging_root(self) -> None:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        root = temp / ("plm-unified-stage-" + uuid.uuid4().hex)
        with self.assertRaises(FileNotFoundError):
            stage(temp / "missing-nonrelease-candidate.zip", root)
        self.assertFalse(root.exists())

    def test_synthetic_stage_rechecks_disk_and_source_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-stage-unit-") as temp:
            parent = Path(temp).resolve(strict=True)
            archive = parent / "synthetic.zip"
            synthetic_archive(archive)
            root = parent / "plm-unified-stage-synthetic01"
            self.assertTrue(root.is_relative_to(parent))
            with (patch("stage_windows_unified_candidate.validate_stage_root", return_value=root),
                  patch("stage_windows_unified_candidate.inspect_candidate",
                        side_effect=lambda path: inspect_candidate(path, expected_sha256=digest_archive(path)))):
                result = stage(archive, root)
            self.assertEqual(result["status"], "NON_RELEASE_STAGING_PASS")
            self.assertFalse(result["installation_performed"])
            self.assertEqual((root / "payload/runtime/python.exe").read_bytes(), b"synthetic")

    def test_source_change_after_copy_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-stage-unit-") as temp:
            parent = Path(temp).resolve(strict=True)
            archive = parent / "synthetic.zip"
            synthetic_archive(archive)
            root = parent / "plm-unified-stage-mutated001"
            with (patch("stage_windows_unified_candidate.validate_stage_root", return_value=root),
                  patch("stage_windows_unified_candidate.inspect_candidate",
                        side_effect=lambda path: inspect_candidate(path, expected_sha256=digest_archive(path))),
                  patch("stage_windows_unified_candidate.digest_archive", return_value="0" * 64)):
                with self.assertRaisesRegex(ValueError, "changed during staging"):
                    stage(archive, root)
            self.assertTrue(root.resolve().is_relative_to(parent))


if __name__ == "__main__":
    unittest.main()
