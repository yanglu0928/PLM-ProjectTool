from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from install_windows_caddy_go_atomic_rehearsal import INTENT_SUFFIX, _write_intent  # noqa: E402
from recover_windows_caddy_go_atomic_rehearsal import discover, inspect, quarantine  # noqa: E402


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.gettempdir()).resolve()
        self.partial = Path(tempfile.mkdtemp(prefix="plm-p39-partial-", dir=self.root))
        self.target = self.root / f"plm-install-rehearsal-p40unit{uuid.uuid4().hex}"
        self.marker = Path(str(self.partial) + INTENT_SUFFIX)
        self.created = [self.partial, self.marker, self.target]
        self.addCleanup(self._clean_exact_test_paths)

    def _clean_exact_test_paths(self) -> None:
        for path in self.created:
            self.assertEqual(path.parent.resolve(), self.root)
            self.assertTrue(path.name.startswith(("plm-p39-partial-", "plm-p39-quarantine-",
                                                  "plm-install-rehearsal-p40unit")))
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            elif path.exists() or path.is_symlink():
                path.unlink()

    def test_owned_incomplete_is_discovered_and_quarantined_without_deletion(self) -> None:
        (self.partial / "incomplete.bin").write_bytes(b"preserved")
        _write_intent(self.partial, self.target)
        self.assertEqual(inspect(self.partial)["status"], "OWNED_INCOMPLETE_PARTIAL")
        self.assertIn(self.partial.name, {item["partial_name"] for item in discover()})
        result = quarantine(self.partial)
        quarantine_root = self.root / result["quarantine_name"]
        quarantine_marker = Path(str(quarantine_root) + INTENT_SUFFIX)
        self.created.extend((quarantine_root, quarantine_marker))
        self.assertEqual((quarantine_root / "incomplete.bin").read_bytes(), b"preserved")
        self.assertTrue(quarantine_marker.is_file())
        self.assertFalse(self.partial.exists())
        self.assertFalse(self.target.exists())
        self.assertFalse(result["file_deleted"])

    def test_unclaimed_partial_is_read_only(self) -> None:
        self.assertEqual(inspect(self.partial)["status"], "UNCLAIMED_PARTIAL")
        with self.assertRaisesRegex(ValueError, "only owned incomplete"):
            quarantine(self.partial)
        self.assertTrue(self.partial.is_dir())

    def test_invalid_intent_is_rejected_without_move(self) -> None:
        self.marker.write_text(json.dumps({"schema_version": 1}), encoding="ascii")
        self.assertEqual(inspect(self.partial)["status"], "INVALID_INTENT_REJECTED")
        with self.assertRaises(ValueError):
            quarantine(self.partial)
        self.assertTrue(self.partial.is_dir())

    def test_existing_target_makes_state_ambiguous(self) -> None:
        _write_intent(self.partial, self.target)
        self.target.mkdir()
        (self.target / "keep.txt").write_text("keep", encoding="ascii")
        self.assertEqual(inspect(self.partial)["status"], "AMBIGUOUS_STATE_REJECTED")
        with self.assertRaises(ValueError):
            quarantine(self.partial)
        self.assertEqual((self.target / "keep.txt").read_text(encoding="ascii"), "keep")

    def test_published_target_with_stale_intent_is_not_quarantined(self) -> None:
        _write_intent(self.partial, self.target)
        self.partial.rmdir()
        self.target.mkdir()
        self.assertEqual(inspect(self.partial)["status"], "PUBLISHED_WITH_STALE_INTENT")
        with self.assertRaises(ValueError):
            quarantine(self.partial)
        self.assertTrue(self.target.is_dir())

    def test_abrupt_child_exit_leaves_recoverable_private_partial(self) -> None:
        tools_dir = str(Path(__file__).resolve().parents[1])
        code = ("import os,sys,tempfile; from pathlib import Path; "
                f"sys.path.insert(0,{tools_dir!r}); "
                "from install_windows_caddy_go_atomic_rehearsal import _write_intent; "
                "p=Path(tempfile.mkdtemp(prefix='plm-p39-partial-')); "
                f"_write_intent(p,Path({str(self.target)!r})); "
                "(p/'half.bin').write_bytes(b'half'); "
                "print(p,flush=True); os._exit(93)")
        child = subprocess.run([sys.executable, "-B", "-c", code],
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 93)
        crashed = Path(child.stdout.strip())
        self.created.extend((crashed, Path(str(crashed) + INTENT_SUFFIX)))
        self.assertEqual(inspect(crashed)["status"], "OWNED_INCOMPLETE_PARTIAL")
        result = quarantine(crashed)
        preserved = self.root / result["quarantine_name"]
        self.created.extend((preserved, Path(str(preserved) + INTENT_SUFFIX)))
        self.assertEqual((preserved / "half.bin").read_bytes(), b"half")


if __name__ == "__main__":
    unittest.main()
