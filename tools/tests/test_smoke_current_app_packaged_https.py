from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smoke_current_app_packaged_https import (  # noqa: E402
    _inputs,
    _prior_archive_attestation,
)


class CurrentAppHttpsBoundaryTests(unittest.TestCase):
    def test_prior_attestation_binds_candidate_name_size_sha_and_nonrelease_flags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "current-app-candidate-test"
            parent.mkdir()
            candidate = parent / "NOT-FOR-RELEASE-windows11-current-app.zip"
            candidate.write_bytes(b"candidate")
            summary = parent / "verification-summary.json"
            summary.write_text(
                '{"archive":"artifacts\\\\current-app-candidate-test\\\\'
                'NOT-FOR-RELEASE-windows11-current-app.zip",'
                '"archive_bytes":9,"archive_sha256":"' + "a" * 64 + '",'
                '"legal_clearance":false,"release_eligible":false,'
                '"status":"WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS"}',
                encoding="utf-8",
            )
            self.assertEqual(_prior_archive_attestation(candidate, "a" * 64, summary),
                             (9, candidate.stat().st_mtime_ns))
            with self.assertRaisesRegex(ValueError, "attestation mismatch"):
                _prior_archive_attestation(candidate, "b" * 64, summary)

    def test_wrong_candidate_digest_rejected_before_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.zip"
            candidate.write_bytes(b"test archive")
            stage = Path(tempfile.gettempdir()) / ("plm-current-app-stage-" + uuid.uuid4().hex[:12])
            stage.mkdir()
            try:
                with self.assertRaisesRegex(ValueError, "identity rejected"):
                    _inputs(candidate, stage, "0" * 64)
            finally:
                stage.rmdir()


if __name__ == "__main__":
    unittest.main()
