from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_windows_current_app_candidate import build_candidate  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CurrentAppCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "parent.zip"
        self.wheel = self.root / "backend.whl"
        self.dist = self.root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "assets" / "index-new.js").write_text("new js", encoding="utf-8")
        (self.dist / "assets" / "index-new.css").write_text("new css", encoding="utf-8")
        (self.dist / "index.html").write_text(
            '<script src="/assets/index-new.js"></script><link href="/assets/index-new.css">',
            encoding="utf-8")
        self.old_payload = {
            "payload/runtime/packages/plm_assistant/__init__.py": b"old app",
            "payload/runtime/packages/plm_assistant/modules/evidence/old.py": b"removed",
            "payload/runtime/packages/plm_project_tool_backend-0.1.0.dev0.dist-info/METADATA": b"old metadata",
            "payload/frontend/dist/index.html": b"old html",
            "payload/frontend/dist/assets/index-old.js": b"old js",
            "payload/frontend/dist/assets/index-old.css": b"old css",
            "payload/ocr/ghostscript/bin/gswin64c.exe": b"third party immutable",
        }
        self._parent(self.old_payload)
        self._wheel()

    def _parent(self, payload: dict[str, bytes], *, checksums: dict[str, str] | None = None) -> None:
        hashes = checksums or {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
        with zipfile.ZipFile(self.parent, "w") as archive:
            for name, data in payload.items():
                archive.writestr(name, data)
            archive.writestr("payload-sha256sums.txt", "".join(
                f"{value}  {name}\n" for name, value in sorted(hashes.items())))
            archive.writestr("third-party-inventory.json", "{\"review\":true}\n")
            archive.writestr("manifest.json", json.dumps({
                "version": "0.1.0.dev0", "payload_file_count": len(payload),
                "release_eligible": False, "legal_clearance": False,
                "formal_tls_material_included": False,
            }))

    def _wheel(self, extra: dict[str, bytes] | None = None) -> None:
        required = {
            "plm_assistant/__init__.py": b"new app",
            "plm_assistant/modules/evidence/api/lookup_eligibility_operation.py": b"lookup router",
            "plm_assistant/migrations/versions/20261001_0052_evidence_parse_provenance.py": b"migration",
            "plm_project_tool_backend-0.1.0.dev0.dist-info/METADATA": b"Version: 0.1.0.dev0\n",
            "plm_project_tool_backend-0.1.0.dev0.dist-info/WHEEL": b"wheel",
            "plm_project_tool_backend-0.1.0.dev0.dist-info/RECORD": b"record",
        }
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, data in {**required, **(extra or {})}.items():
                archive.writestr(name, data)

    def _build(self) -> dict[str, object]:
        return build_candidate(self.parent, self.wheel, self.dist, self.root,
                               "a" * 40, expected_parent_sha256=digest(self.parent))

    def test_replaces_only_app_and_frontend_with_complete_checksums(self) -> None:
        result = self._build()
        self.assertEqual(result["status"], "WINDOWS11_CURRENT_APP_NON_RELEASE_INTEGRITY_PASS")
        self.assertFalse(result["release_eligible"])
        with zipfile.ZipFile(result["archive"]) as archive:
            names = set(archive.namelist())
            self.assertNotIn("payload/runtime/packages/plm_assistant/modules/evidence/old.py", names)
            self.assertNotIn("payload/frontend/dist/assets/index-old.js", names)
            self.assertEqual(archive.read("payload/runtime/packages/plm_assistant/__init__.py"), b"new app")
            self.assertEqual(archive.read("payload/ocr/ghostscript/bin/gswin64c.exe"),
                             b"third party immutable")
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["source_git_commit"], "a" * 40)
            self.assertFalse(manifest["legal_clearance"])
            self.assertEqual(manifest["payload_file_count"], len(names) - 3)

    def test_parent_payload_tamper_and_unsafe_wheel_fail_closed(self) -> None:
        wrong = {**self.old_payload, "payload/ocr/ghostscript/bin/gswin64c.exe": b"tampered"}
        original_hashes = {name: hashlib.sha256(data).hexdigest()
                           for name, data in self.old_payload.items()}
        self._parent(wrong, checksums=original_hashes)
        with self.assertRaisesRegex(ValueError, "parent payload hash mismatch"):
            self._build()
        self._parent(self.old_payload)
        self._wheel({"../secret.txt": b"secret"})
        with self.assertRaises(ValueError):
            self._build()

    def test_missing_current_migration_and_bad_frontend_fail_closed(self) -> None:
        # A missing expected migration is rejected even if the wheel otherwise loads.
        with zipfile.ZipFile(self.wheel, "w") as archive:
            archive.writestr("plm_assistant/__init__.py", b"new app")
        with self.assertRaisesRegex(ValueError, "wheel lacks current"):
            self._build()
        self._wheel()
        (self.dist / "index.html").write_text("no assets", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not referenced"):
            self._build()


if __name__ == "__main__":
    unittest.main()
