from __future__ import annotations
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage_windows_parent_candidate_offline as cli  # noqa: E402

class OfflineParentCandidateStagingCliTests(unittest.TestCase):
    def test_success_receipt_is_limited_and_does_not_echo_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-a40-cli-") as temp:
            root = Path(temp)
            argv = ["stage", "--candidate", str(root / "candidate.zip"),
                    "--verification-summary", str(root / "summary.json"),
                    "--target", str(root / "staged")]
            expected = {"status": cli.HOSTED_RECEIPT_STATUS, "archive_sha256": "a" * 64,
                        "payload_file_count": 3, "release_eligible": False,
                        "legal_clearance": False, "installation_performed": False,
                        "services_started": False}
            output = io.StringIO()
            with patch.object(sys, "argv", argv):
                with patch.object(cli, "stage_candidate", return_value=expected):
                    with contextlib.redirect_stdout(output):
                        result = cli.main()
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), expected)
        self.assertNotIn(str(root), output.getvalue())

    def test_rejection_does_not_echo_exception_text_or_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-a40-reject-") as temp:
            root = Path(temp)
            output = io.StringIO()
            argv = ["stage", "--candidate", str(root / "candidate.zip"),
                    "--verification-summary", str(root / "summary.json"),
                    "--target", str(root / "staged")]
            with patch.object(sys, "argv", argv):
                with patch.object(cli, "stage_candidate", side_effect=ValueError(f"secret-like {root}")):
                    with contextlib.redirect_stdout(output):
                        result = cli.main()
        report = json.loads(output.getvalue())
        self.assertEqual(result, 2)
        self.assertEqual(report["status"], "HOSTED_WINDOWS_CANDIDATE_STAGING_REJECTED")
        self.assertEqual(report["reason_code"], "ValueError")
        self.assertFalse(report["installation_performed"])
        self.assertNotIn(str(root), output.getvalue())

    def test_wrong_external_archive_digest_is_rejected_before_target_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-a40-bad-digest-") as temp:
            root = Path(temp)
            runner_temp = root / "runner-temp"
            runner_temp.mkdir()
            candidate = root / "candidate.zip"
            candidate.write_bytes(b"synthetic archive")
            summary = root / "summary.json"
            summary.write_text(json.dumps({
                "status": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS",
                "release_eligible": False, "legal_clearance": False,
                "archive_sha256": "0" * 64,
            }), encoding="utf-8")
            target = runner_temp / "staged"
            with patch.dict(os.environ, {"RUNNER_TEMP": str(runner_temp)}):
                from stage_windows_parent_candidate_cloud import stage_candidate
                with self.assertRaisesRegex(ValueError, "summary or archive identity"):
                    stage_candidate(candidate, summary, target,
                                    receipt_status=cli.HOSTED_RECEIPT_STATUS)
            self.assertFalse(target.exists())

if __name__ == "__main__":
    unittest.main()
