from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stage_windows_current_app_candidate import stage  # noqa: E402


class StageCurrentAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / "candidate.zip"
        self.root = Path(tempfile.gettempdir()) / ("plm-current-app-stage-" + uuid.uuid4().hex[:12])
        self.addCleanup(lambda: self._cleanup_stage())
        payload = {"payload/runtime/packages/plm_assistant/__init__.py": b"current"}
        with zipfile.ZipFile(self.archive, "w") as output:
            for name, data in payload.items():
                output.writestr(name, data)
            output.writestr("payload-sha256sums.txt", "".join(
                hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                for name, data in payload.items()))
            output.writestr("third-party-inventory.json", "{}\n")
            output.writestr("manifest.json", json.dumps({
                "kind": "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE",
                "payload_file_count": len(payload), "release_eligible": False,
                "legal_clearance": False, "formal_tls_material_included": False,
                "source_git_commit": "a" * 40,
            }))
        self.digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def _cleanup_stage(self) -> None:
        if self.root.exists():
            import shutil
            if (self.root.resolve().parent != Path(tempfile.gettempdir()).resolve() or
                    not self.root.name.startswith("plm-current-app-stage-")):
                raise RuntimeError("test cleanup target escaped Temp")
            shutil.rmtree(self.root)

    def test_clean_extract_and_fail_closed_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            stage(self.archive, self.root, "0" * 64)
        self.assertFalse(self.root.exists())
        result = stage(self.archive, self.root, self.digest)
        self.assertEqual(result["status"], "NON_RELEASE_CURRENT_APP_CLEAN_EXTRACT_PASS")
        self.assertFalse(result["release_eligible"])
        with self.assertRaisesRegex(ValueError, "fresh direct ASCII"):
            stage(self.archive, self.root, self.digest)


if __name__ == "__main__":
    unittest.main()
