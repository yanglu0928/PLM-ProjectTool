from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_windows_unified_caddy_install import META, exact_mapping  # noqa: E402
from smoke_current_app_packaged_https import (  # noqa: E402
    _inputs,
    _prior_archive_attestation,
    _target_rehearsal,
    _app_projection_hashes,
)


class CurrentAppHttpsBoundaryTests(unittest.TestCase):
    def test_target_rehearsal_uses_upgrade_callback_and_requires_evidence(self) -> None:
        candidate = Path("candidate.zip")
        stage = Path("stage")
        target = Path("target")
        seen = []

        def upgrade(_candidate, _source, _stage, layout):
            seen.append(layout)
            return {"status": "UPGRADED_LAYOUT_READY", "layout": str(layout)}

        evidence = _target_rehearsal(upgrade, lambda *_: self.fail("default used"),
                                     candidate, stage, target)
        self.assertEqual(seen, [target])
        self.assertEqual(evidence["status"], "UPGRADED_LAYOUT_READY")
        with self.assertRaisesRegex(ValueError, "return evidence"):
            _target_rehearsal(lambda *_: None, upgrade, candidate, stage, target)

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


    def test_parent_startup_diagnostic_is_excluded_from_app_projection_only(self) -> None:
        parent_hashes = {
            "payload/check-startup.ps1": "a" * 64,
            "payload/runtime/python.exe": "b" * 64,
        }
        projected = _app_projection_hashes(parent_hashes)
        self.assertEqual(projected, {"payload/runtime/python.exe": "b" * 64})
        self.assertEqual(len(parent_hashes), 2)
        self.assertEqual(len(projected), 1)
        self.assertIn("payload/check-startup.ps1", parent_hashes)

    def test_other_unmapped_parent_assets_remain_for_strict_rejection(self) -> None:
        parent_hashes = {
            "payload/check-startup.ps1": "a" * 64,
            "payload/future/unknown.bin": "b" * 64,
        }
        projected = _app_projection_hashes(parent_hashes)
        self.assertEqual(set(projected), {"payload/future/unknown.bin"})
        with self.assertRaisesRegex(ValueError, "unmapped candidate payload family"):
            exact_mapping([*projected, *META])

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
