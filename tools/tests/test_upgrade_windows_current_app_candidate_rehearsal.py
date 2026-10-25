from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upgrade_windows_current_app_candidate_rehearsal as upgrade


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class UpgradeRehearsalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_context.cleanup)
        self.temp = Path(self.temp_context.name)
        self.temp_patch = patch.object(upgrade.tempfile, "gettempdir", return_value=str(self.temp))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.root = self.temp / "plm-current-app-upgrade-test-token"
        self.root.mkdir()
        self.old = {"payload/old.txt": hashlib.sha256(b"old").hexdigest()}
        self.new = {"payload/new.txt": hashlib.sha256(b"new").hexdigest()}
        self.old_map = {"payload/old.txt": "app/old.txt"}
        self.new_map = {"payload/new.txt": "app/new.txt"}
        for name in ("data", "config", "license", "plugins"):
            (self.root / name).mkdir()
            (self.root / name / "synthetic.marker").write_text(name, encoding="ascii")
        (self.root / "app").mkdir()
        (self.root / "app" / "old.txt").write_text("old", encoding="ascii")
        self.old_candidate_sha = "a" * 64
        self.new_candidate_sha = "b" * 64
        self.token = "owner-token-0123456789"
        upgrade.initialize_rehearsal(self.root, owner_token=self.token,
                                      old_candidate_sha256=self.old_candidate_sha,
                                      new_candidate_sha256=self.new_candidate_sha)
        self.next_root = self.temp / "plm-current-app-next-test-token"
        self.next_root.mkdir()
        (self.next_root / "app").mkdir()
        (self.next_root / "app" / "new.txt").write_text("new", encoding="ascii")
        self.markers = self._marker_snapshot()
        self.kwargs = dict(owner_token=self.token, old_expected=self.old, old_mapping=self.old_map,
                           new_expected=self.new, new_mapping=self.new_map,
                           old_candidate_sha256=self.old_candidate_sha,
                           new_candidate_sha256=self.new_candidate_sha)

    def _marker_snapshot(self):
        return {str(path.relative_to(self.root)): (path.read_bytes(), _sha(path))
                for folder in ("data", "config", "license", "plugins")
                for path in (self.root / folder).rglob("*") if path.is_file()}

    def _assert_markers_unchanged(self) -> None:
        self.assertEqual(self._marker_snapshot(), self.markers)

    def test_failed_activation_requires_explicit_restore_and_preserves_both_payloads(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "after activating"):
            upgrade.switch_prepared_payload(self.root, self.next_root, fail_at="new_active", **self.kwargs)
        self.assertEqual((self.root / "app" / "new.txt").read_text(encoding="ascii"), "new")
        self.assertEqual((self.root / upgrade.PREVIOUS_DIR / "app" / "old.txt").read_text(encoding="ascii"), "old")
        self.assertEqual(json.loads((self.root / upgrade.OWNER_FILE).read_text(encoding="ascii"))["state"], "NEW_ACTIVE")
        self._assert_markers_unchanged()
        result = upgrade.restore_prepared_payload(self.root, **self.kwargs)
        self.assertFalse(result["automatic_rollback_performed"])
        self.assertTrue(result["failed_payload_preserved"])
        self.assertEqual((self.root / "app" / "old.txt").read_text(encoding="ascii"), "old")
        self.assertEqual((self.root / upgrade.FAILED_DIR / "app" / "new.txt").read_text(encoding="ascii"), "new")
        self._assert_markers_unchanged()

    def test_prepared_failure_keeps_old_payload_active(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "after payload preparation"):
            upgrade.switch_prepared_payload(self.root, self.next_root, fail_at="prepared", **self.kwargs)
        self.assertEqual((self.root / "app" / "old.txt").read_text(encoding="ascii"), "old")
        self.assertEqual((self.next_root / "app" / "new.txt").read_text(encoding="ascii"), "new")
        self.assertFalse((self.root / upgrade.PREVIOUS_DIR / "app").exists())
        self._assert_markers_unchanged()

    def test_failure_after_saving_previous_is_recoverable_explicitly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "after saving previous"):
            upgrade.switch_prepared_payload(self.root, self.next_root, fail_at="previous_saved", **self.kwargs)
        self.assertFalse((self.root / "app").exists())
        self.assertTrue((self.root / upgrade.PREVIOUS_DIR / "app" / "old.txt").exists())
        result = upgrade.restore_prepared_payload(self.root, **self.kwargs)
        self.assertEqual(result["status"], "NON_RELEASE_CURRENT_APP_MANUAL_RESTORE_PASS")
        self.assertTrue((self.root / "app" / "old.txt").exists())
        self._assert_markers_unchanged()

    def test_ownership_mismatch_is_rejected_without_mutation(self) -> None:
        with self.assertRaisesRegex(ValueError, "ownership mismatch"):
            upgrade.switch_prepared_payload(
                self.root, self.next_root,
                **{**self.kwargs, "owner_token": "wrong-token-012345"},
            )
        self.assertTrue((self.root / "app" / "old.txt").exists())
        self.assertTrue((self.next_root / "app" / "new.txt").exists())
        self._assert_markers_unchanged()

    def test_successful_switch_reports_nonrelease_pass_without_automatic_rollback(self) -> None:
        result = upgrade.switch_prepared_payload(self.root, self.next_root, **self.kwargs)
        self.assertEqual(result["status"], "NON_RELEASE_CURRENT_APP_UPGRADE_PASS")
        self.assertFalse(result["automatic_rollback_performed"])
        self.assertEqual((self.root / "app" / "new.txt").read_text(encoding="ascii"), "new")
        self.assertEqual((self.root / upgrade.PREVIOUS_DIR / "app" / "old.txt").read_text(encoding="ascii"), "old")
        self._assert_markers_unchanged()


if __name__ == "__main__":
    unittest.main()
