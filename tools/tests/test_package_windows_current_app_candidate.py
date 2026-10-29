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
from package_windows_current_app_candidate import (  # noqa: E402
    SCRATCH_EXCLUDE_PATHSPEC, _untracked_outside_user_scratch, build_candidate,
)
from smoke_packaged_pg18_migration import _migration_temp_root  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CurrentAppCandidateTests(unittest.TestCase):
    def test_nested_pg_smoke_prefers_owned_a17_root_and_rejects_escape(self) -> None:
        runner_temp = Path(os.environ["RUNNER_TEMP"])
        with tempfile.TemporaryDirectory(dir=runner_temp) as temporary:
            runner = Path(temporary)
            run_root = runner / "plm-p51-a27-test"
            owned = run_root / "PLMToolTemp"
            pg_owned = runner / "plm-p51-a27-pg-123"
            owned.mkdir(parents=True)
            pg_owned.mkdir()
            with patch.dict(os.environ, {
                "RUNNER_TEMP": str(runner),
                "GITHUB_RUN_ID": "123",
                "PLM_P51_TEMP_ROOT": str(owned),
                "PLM_PG_TEMP_ROOT": str(pg_owned),
            }, clear=True):
                self.assertEqual(_migration_temp_root(), pg_owned.resolve())
            with patch.dict(os.environ, {
                "RUNNER_TEMP": str(runner),
                "GITHUB_RUN_ID": "123",
                "PLM_P51_TEMP_ROOT": str(owned),
                "PLM_PG_TEMP_ROOT": str(runner / "outside"),
            }, clear=True):
                with self.assertRaisesRegex(ValueError, "outside this run"):
                    _migration_temp_root()
            with patch.dict(os.environ, {
                "RUNNER_TEMP": str(runner),
                "PLM_P51_TEMP_ROOT": str(owned),
            }, clear=True):
                self.assertEqual(_migration_temp_root(), owned.resolve())

            escaped = runner / "outside"
            escaped.mkdir()
            with patch.dict(os.environ, {
                "RUNNER_TEMP": str(runner),
                "PLM_P51_TEMP_ROOT": str(escaped),
            }, clear=True):
                with self.assertRaisesRegex(ValueError, "outside the owned"):
                    _migration_temp_root()

    def test_nested_pg_smoke_uses_system_temp_without_a17_root(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_migration_temp_root(), Path(tempfile.gettempdir()).resolve())

    def test_cleanliness_check_excludes_only_user_tmp_tree(self) -> None:
        with patch("package_windows_current_app_candidate.subprocess.check_output",
                   return_value="") as check:
            self.assertFalse(_untracked_outside_user_scratch())
        args = check.call_args.args[0]
        self.assertEqual(args[-1], SCRATCH_EXCLUDE_PATHSPEC)
        self.assertEqual(SCRATCH_EXCLUDE_PATHSPEC, ":(exclude).tmp/**")
        check.return_value = "?? docs/untracked-result.md"
        with patch("package_windows_current_app_candidate.subprocess.check_output",
                   return_value=check.return_value):
            self.assertTrue(_untracked_outside_user_scratch())

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "parent.zip"
        self.wheel = self.root / "backend.whl"
        self.pgvector_wheel = self.root / "pgvector.whl"
        self.dist = self.root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "assets" / "index-a1b2c3d4.js").write_text("new js", encoding="utf-8")
        (self.dist / "assets" / "index-e5f6g7h8.css").write_text("new css", encoding="utf-8")
        (self.dist / "index.html").write_text(
            '<script src="/assets/index-a1b2c3d4.js"></script>'
            '<link href="/assets/index-e5f6g7h8.css">',
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
        self._pgvector()

    def _parent(self, payload: dict[str, bytes], *, checksums: dict[str, str] | None = None) -> None:
        hashes = checksums or {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
        with zipfile.ZipFile(self.parent, "w") as archive:
            for name, data in payload.items():
                archive.writestr(name, data)
            archive.writestr("payload-sha256sums.txt", "".join(
                f"{value}  {name}\n" for name, value in sorted(hashes.items())))
            archive.writestr("third-party-inventory.json", "{\"review\":true}\n")
            archive.writestr("manifest.json", json.dumps({
                "version": "0.1.0.dev0", "kind": "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE",
                "payload_file_count": len(payload),
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

    def _pgvector(self, extra: dict[str, bytes] | None = None) -> None:
        required = {
            "pgvector/__init__.py": b"pgvector",
            "pgvector/sqlalchemy/__init__.py": b"sqlalchemy",
            "pgvector-0.5.0.dist-info/METADATA":
                b"Name: pgvector\nVersion: 0.5.0\nLicense-Expression: MIT\n",
            "pgvector-0.5.0.dist-info/WHEEL": b"wheel",
            "pgvector-0.5.0.dist-info/RECORD": b"record",
            "pgvector-0.5.0.dist-info/licenses/LICENSE.txt": b"MIT",
        }
        with zipfile.ZipFile(self.pgvector_wheel, "w") as archive:
            for name, data in {**required, **(extra or {})}.items():
                archive.writestr(name, data)

    def _build(self) -> dict[str, object]:
        return build_candidate(self.parent, self.wheel, self.dist, self.root,
                               "a" * 40, self.pgvector_wheel,
                               expected_parent_sha256=digest(self.parent),
                               expected_pgvector_sha256=digest(self.pgvector_wheel))

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
            self.assertEqual(archive.read("payload/runtime/packages/pgvector/__init__.py"),
                             b"pgvector")
            inventory = json.loads(archive.read("third-party-inventory.json"))
            self.assertEqual(inventory["python_runtime_additions"][0]["name"], "pgvector")
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

    def test_hashed_frontend_chunks_are_included_and_unexpected_files_rejected(self) -> None:
        (self.dist / "assets" / "ReviewPanel-B1c2D3e4.js").write_text("chunk js", encoding="utf-8")
        (self.dist / "assets" / "ReviewPanel-B1c2D3e4.css").write_text("chunk css", encoding="utf-8")
        result = self._build()
        with zipfile.ZipFile(result["archive"]) as archive:
            names = set(archive.namelist())
            self.assertIn("payload/frontend/dist/assets/ReviewPanel-B1c2D3e4.js", names)
            self.assertIn("payload/frontend/dist/assets/ReviewPanel-B1c2D3e4.css", names)
            manifest = json.loads(archive.read("manifest.json"))
            self.assertIn("payload/frontend/dist/assets/ReviewPanel-B1c2D3e4.js",
                          manifest["frontend_sha256"])
        (self.dist / "assets" / "debug.js.map").write_text("source map", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unexpected frontend dist layout"):
            self._build()

    def test_pgvector_wheel_identity_and_hash_fail_closed(self) -> None:
        self._pgvector({"../unsafe.txt": b"bad"})
        with self.assertRaises(ValueError):
            self._build()
        self._pgvector()
        with self.assertRaisesRegex(ValueError, "pgvector wheel SHA-256 mismatch"):
            build_candidate(self.parent, self.wheel, self.dist, self.root,
                            "a" * 40, self.pgvector_wheel,
                            expected_parent_sha256=digest(self.parent),
                            expected_pgvector_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
