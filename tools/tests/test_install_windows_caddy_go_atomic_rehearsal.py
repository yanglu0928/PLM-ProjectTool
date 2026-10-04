from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from install_windows_caddy_go_atomic_rehearsal import (  # noqa: E402
    _copy_and_publish, rehearse,
)


class AtomicInstallRehearsalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stage_context = tempfile.TemporaryDirectory(prefix="plm-p39-unit-source-")
        self.addCleanup(self.stage_context.cleanup)
        self.stage = Path(self.stage_context.name)
        self.target = Path(tempfile.gettempdir()) / f"plm-install-rehearsal-p39unit{uuid.uuid4().hex}"
        self.assertFalse(self.target.exists())
        self.addCleanup(self._clean_owned_target)
        self.mapping = {"one.bin": "app/one.bin", "two.bin": "runtime/two.bin"}
        self.hashes = {}
        for name, body in (("one.bin", b"one"), ("two.bin", b"two")):
            (self.stage / name).write_bytes(body)
            self.hashes[name] = hashlib.sha256(body).hexdigest()

    def _clean_owned_target(self) -> None:
        self.assertEqual(self.target.parent.resolve(), Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.target.name.startswith("plm-install-rehearsal-p39unit"))
        if self.target.exists():
            shutil.rmtree(self.target)

    def test_complete_copy_publishes_only_after_readback(self) -> None:
        result = _copy_and_publish(self.stage, self.target, self.mapping, self.hashes)
        self.assertEqual(result["target_file_count"], 2)
        self.assertFalse(result["release_eligible"])
        self.assertEqual((self.target / "app/one.bin").read_bytes(), b"one")
        self.assertEqual((self.target / "runtime/two.bin").read_bytes(), b"two")
        self.assertTrue(all((self.target / name).is_dir()
                            for name in ("plugins", "data", "logs", "license")))

    def test_copy_interruption_removes_only_private_partial(self) -> None:
        parent = Path(tempfile.gettempdir())
        before = {path.name for path in parent.glob("plm-p39-partial-*")}
        with self.assertRaisesRegex(RuntimeError, "injected copy interruption"):
            _copy_and_publish(self.stage, self.target, self.mapping, self.hashes, fail_after=1)
        self.assertFalse(self.target.exists())
        self.assertEqual(before, {path.name for path in parent.glob("plm-p39-partial-*")})
        self.assertEqual((self.stage / "one.bin").read_bytes(), b"one")

    def test_existing_target_rejected_without_overwrite(self) -> None:
        self.target.mkdir()
        (self.target / "user.txt").write_text("keep", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "fresh direct ASCII Temp child"):
            _copy_and_publish(self.stage, self.target, self.mapping, self.hashes)
        self.assertEqual((self.target / "user.txt").read_text(encoding="ascii"), "keep")

    def test_unverified_source_rejected_before_copy(self) -> None:
        with patch("install_windows_caddy_go_atomic_rehearsal.verify_candidate",
                   side_effect=ValueError("candidate rejected")):
            with self.assertRaisesRegex(ValueError, "candidate rejected"):
                rehearse(Path("candidate"), Path("source"), self.stage, self.target)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
