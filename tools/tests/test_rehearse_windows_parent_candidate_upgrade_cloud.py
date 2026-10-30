from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehearse_windows_parent_candidate_upgrade_cloud import (  # noqa: E402
    _activate,
    _install_initial,
    _manual_restore,
    _marker_hashes,
    _owned_child,
    _read_checksums,
    run,
    _verify_candidate,
)


class ParentCandidateUpgradeCloudTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.name != "nt":
            self.skipTest("A34 file replacement contract is hosted-Windows specific")
        self.runner_temp = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        self.temp = Path(tempfile.mkdtemp(prefix="plm-a34-test-", dir=self.runner_temp))

    def tearDown(self) -> None:
        if self.temp.exists():
            import shutil

            shutil.rmtree(self.temp)

    def _stage(self, name: str, content: bytes) -> tuple[Path, dict[str, str]]:
        stage = self.temp / name
        payload = stage / "payload" / "app"
        payload.mkdir(parents=True)
        (payload / "version.txt").write_bytes(content)
        relative = "payload/app/version.txt"
        digest = hashlib.sha256(content).hexdigest()
        (stage / "payload-sha256sums.txt").write_text(
            f"{digest}  {relative}\n", encoding="ascii"
        )
        (stage / "manifest.json").write_text(
            json.dumps({"kind": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE",
                        "release_eligible": False, "legal_clearance": False}),
            encoding="utf-8",
        )
        return stage, {relative: digest}

    def _candidate(self, name: str, workflow_run: str, version: bytes) -> tuple[Path, Path]:
        payload = {
            "payload/app/version.txt": version,
        }
        blocker_codes = [
            "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
            "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
            "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
            "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
            "TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",
        ]
        report = {
            "status": "BLOCKED",
            "release_eligible": False,
            "legal_clearance": False,
            "blocker_codes": sorted(blocker_codes + ["NON_RELEASE_CANDIDATE"]),
        }
        launcher = (
            "[Console]::Out.WriteLine('" + json.dumps(report, separators=(",", ":")) + "')\n"
            "[Console]::Error.WriteLine('Packaged startup blocked; see BLOCKED diagnostics above.')\n"
            "exit 1\n"
        ).encode("ascii")
        payload["payload/start-trial.ps1"] = launcher
        payload["provenance/a34-synthetic-evidence.json"] = b'{"kind":"synthetic"}\n'
        hashes = {path: hashlib.sha256(data).hexdigest()
                  for path, data in payload.items()}
        checksum_bytes = "".join(
            f"{hashes[path]}  {path}\n" for path in sorted(hashes)
        ).encode("ascii")
        manifest = {
            "kind": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE",
            "release_eligible": False,
            "legal_clearance": False,
            "source_commit": "a34-synthetic-" + name,
            "workflow_run": workflow_run,
            "payload_file_count": len(payload),
            "payload_sha256sums_sha256": hashlib.sha256(checksum_bytes).hexdigest(),
            "startup_preflight": {"blocker_codes": blocker_codes},
        }
        archive = self.temp / (name + ".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest).encode("utf-8"))
            bundle.writestr("payload-sha256sums.txt", checksum_bytes)
            for path, data in payload.items():
                bundle.writestr(path, data)
        summary = {
            "status": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS",
            "release_eligible": False,
            "legal_clearance": False,
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "payload_file_count": len(payload),
            "source_commit": manifest["source_commit"],
            "workflow_run": workflow_run,
        }
        summary_path = self.temp / (name + "-verification-summary.json")
        summary_path.write_text(json.dumps(summary), encoding="utf-8")
        return archive, summary_path

    def test_checksum_inventory_rejects_traversal(self) -> None:
        stage = self.temp / "invalid-stage"
        (stage / "payload").mkdir(parents=True)
        digest = hashlib.sha256(b"x").hexdigest()
        (stage / "payload-sha256sums.txt").write_text(
            f"{digest}  payload/../outside\n", encoding="ascii"
        )
        with self.assertRaises(ValueError):
            _read_checksums(stage)

    def test_owned_child_rejects_existing_root_and_c_drive(self) -> None:
        existing = self.temp / "plm-a34-run-existing"
        existing.mkdir()
        with self.assertRaises(ValueError):
            _owned_child(existing, self.temp, "plm-a34-run-", fresh=True)
        if self.runner_temp.drive.casefold() != "c:":
            with self.assertRaises(ValueError):
                _owned_child(Path("C:/plm-a34-run-forbidden"), self.runner_temp,
                             "plm-a34-run-", fresh=True)

    def test_explicit_restore_returns_previous_candidate_and_preserves_markers(self) -> None:
        old_stage, old_hashes = self._stage("old-stage", b"old candidate")
        new_stage, new_hashes = self._stage("new-stage", b"new candidate")
        target = self.temp / "plm-a34-run-test"
        backup = self.temp / "plm-a34-backup-test"
        failed = self.temp / "plm-a34-failed-test"

        _install_initial(old_stage, target, old_hashes)
        markers = _marker_hashes(target)
        _activate(new_stage, target, backup, new_hashes)
        _verify_candidate(new_stage, target, new_hashes)
        self.assertEqual(markers, _marker_hashes(target))

        _manual_restore(target, backup, failed)
        _verify_candidate(old_stage, target, old_hashes)
        self.assertEqual(markers, _marker_hashes(target))
        self.assertTrue((failed / "payload/app/version.txt").is_file())

    def test_run_rehearses_verified_package_failure_restore_and_startup_refusal(self) -> None:
        current_run = "41008231772"
        old_archive, old_summary = self._candidate("old", "40995913354", b"old")
        new_archive, new_summary = self._candidate("current", current_run, b"current")
        work_root = self.runner_temp / ("plm-a34-run-test-" + os.urandom(8).hex())
        with patch.dict(os.environ, {"GITHUB_RUN_ID": current_run}):
            result = run(old_archive, old_summary, new_archive, new_summary, work_root)
        self.assertEqual(result["status"], "PLT_PKG_01_A09_P51_A34_PASS_LIMITED")
        self.assertEqual(result["persistent_marker_count"], 4)
        self.assertTrue(result["persistent_markers_preserved"])
        self.assertFalse(result["automatic_rollback_performed"])
        self.assertTrue(result["explicit_manual_restore_passed"])
        self.assertTrue(result["new_candidate_remained_active_until_manual_restore"])
        self.assertTrue(result["failed_candidate_quarantined"])
        self.assertTrue(result["provenance_preserved_in_quarantine"])
        self.assertEqual(result["launcher_after_upgrade"]["status"], "BLOCKED")
        self.assertFalse(work_root.exists())


if __name__ == "__main__":
    unittest.main()
