from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehearse_windows_parent_candidate_upgrade_cloud import (  # noqa: E402
    _activate,
    _install_initial,
    _manual_restore,
    _marker_hashes,
    _owned_child,
    _read_checksums,
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


if __name__ == "__main__":
    unittest.main()
