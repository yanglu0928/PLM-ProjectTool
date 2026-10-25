from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rehearse_current_app_directory_upgrade import (  # noqa: E402
    _stage_inventory,
    _verify,
    rehearse_upgrade,
    restore_previous,
)


def _stage(name: str, content: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="plm-current-app-stage-test-", dir=tempfile.gettempdir()))
    files = {
        "payload/runtime/packages/plm_assistant/probe.py": ("runtime:" + content).encode("ascii"),
        "payload/frontend/dist/index.html": ("app:" + content).encode("ascii"),
    }
    (root / "payload").mkdir()
    for relative, data in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    lines = [hashlib.sha256(data).hexdigest() + "  " + relative for relative, data in files.items()]
    (root / "payload-sha256sums.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    for metadata in ("manifest.json", "third-party-inventory.json"):
        (root / metadata).write_text("{}", encoding="ascii")
    return root


class CurrentAppDirectoryUpgradeTests(unittest.TestCase):
    def test_failure_stays_active_until_explicit_manual_restore(self) -> None:
        token = uuid.uuid4().hex
        old, new = _stage("old", "old"), _stage("new", "new")
        target = Path(tempfile.gettempdir()) / ("plm-install-rehearsal-a16t-" + token)
        backup = Path(tempfile.gettempdir()) / ("plm-install-rehearsal-a16b-" + token)
        try:
            old_hashes, old_mapping = _stage_inventory(old)
            new_hashes, new_mapping = _stage_inventory(new)
            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                rehearse_upgrade(old, new, target, fail_at="new_active")
            persistent = {p.relative_to(target).as_posix() for folder in ("plugins", "data", "config", "license")
                          for p in (target / folder).glob("a16-*.marker")}
            _verify(target, new_hashes, new_mapping, persistent)
            result = restore_previous(target, backup)
            self.assertEqual(result["status"], "A16_MANUAL_RESTORE_PASS")
            self.assertFalse(result["automatic_rollback_performed"] if "automatic_rollback_performed" in result else False)
            _verify(target, old_hashes, old_mapping, persistent)
            self.assertTrue(Path(str(result["failed_root"])).is_dir())
            shutil.rmtree(Path(str(result["failed_root"])))
        finally:
            for path in (target, backup, old, new):
                if path.exists():
                    shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
