from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("license_augment", TOOLS / "augment_windows_candidate_licenses.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AugmentTests(unittest.TestCase):
    def _sidecar(self, root: Path, *, candidate_hash: str = "a" * 64, tamper: bool = False) -> Path:
        path = root / "sidecar.zip"
        files = []
        with zipfile.ZipFile(path, "w") as archive:
            for index in range(152):
                name = f"notices/synthetic-1.whl/LICENSE-{index}.txt"
                data = f"synthetic {index}".encode()
                files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "source_wheel_sha256": "b" * 64})
                archive.writestr(name, b"tampered" if tamper and index == 0 else data)
            archive.writestr("manifest.json", json.dumps({
                "kind": "WINDOWS11_WHEEL_LICENSE_SIDECAR_NOT_FOR_RELEASE",
                "release_eligible": False,
                "review_status": "REVIEW_REQUIRED",
                "candidate_sha256": candidate_hash,
                "wheel_count": 93,
                "notice_file_count": 152,
                "files": files,
            }))
        return path

    def test_sidecar_complete_exact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            sidecar = self._sidecar(Path(temp))
            self.assertEqual(len(MODULE.inspect_sidecar(sidecar, "a" * 64)), 152)

    def test_sidecar_wrong_candidate_or_tamper_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sidecar = self._sidecar(root, tamper=True)
            with self.assertRaisesRegex(ValueError, "source or release gate"):
                MODULE.inspect_sidecar(sidecar, "c" * 64)
            with self.assertRaisesRegex(ValueError, "notice hash mismatch"):
                MODULE.inspect_sidecar(sidecar, "a" * 64)


if __name__ == "__main__":
    unittest.main()
