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
SPEC = importlib.util.spec_from_file_location("frontend_augment", TOOLS / "augment_windows_candidate_frontend_licenses.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendAugmentTests(unittest.TestCase):
    def _fixture(self, root: Path, *, tamper: bool = False) -> tuple[Path, Path]:
        candidate = root / "candidate.zip"
        assets = {"index.html": b"html", "assets/a.js": b"js", "assets/a.css": b"css"}
        with zipfile.ZipFile(candidate, "w") as archive:
            for name, data in assets.items():
                archive.writestr("payload/frontend/dist/" + name, data)
        sidecar = root / "sidecar.zip"
        files = []
        with zipfile.ZipFile(sidecar, "w") as archive:
            for index in range(6):
                name = f"notices/package-{index}/1.0/LICENSE"
                data = f"license {index}".encode()
                archive.writestr(name, b"tampered" if tamper and index == 0 else data)
                files.append({"path": name, "sha256": hashlib.sha256(data).hexdigest()})
            archive.writestr("manifest.json", json.dumps({
                "kind": "FRONTEND_LICENSE_SIDECAR_NOT_FOR_RELEASE",
                "release_eligible": False, "review_status": "REVIEW_REQUIRED",
                "package_count": 6, "license_file_count": 6,
                "frozen_dist_hashes": {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()},
                "files": files,
            }))
        return candidate, sidecar

    def test_sidecar_and_candidate_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, sidecar = self._fixture(Path(temp))
            _, files = MODULE.inspect_frontend_sidecar(sidecar, candidate)
            self.assertEqual(len(files), 6)
            with zipfile.ZipFile(candidate, "w") as archive:
                archive.writestr("payload/frontend/dist/index.html", b"changed")
                archive.writestr("payload/frontend/dist/assets/a.js", b"js")
                archive.writestr("payload/frontend/dist/assets/a.css", b"css")
            with self.assertRaisesRegex(ValueError, "dist mismatch"):
                MODULE.inspect_frontend_sidecar(sidecar, candidate)

    def test_tampered_notice_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, sidecar = self._fixture(Path(temp), tamper=True)
            with self.assertRaisesRegex(ValueError, "notice hash mismatch"):
                MODULE.inspect_frontend_sidecar(sidecar, candidate)


if __name__ == "__main__":
    unittest.main()
