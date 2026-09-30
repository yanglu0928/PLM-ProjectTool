from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "package_windows_embedded_candidate.py"
SPEC = importlib.util.spec_from_file_location("embedded_candidate", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
VERIFY_PATH = Path(__file__).resolve().parents[1] / "verify_windows11_embedded_candidate.py"
VERIFY_SPEC = importlib.util.spec_from_file_location("verify_embedded_candidate", VERIFY_PATH)
assert VERIFY_SPEC and VERIFY_SPEC.loader
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


class CandidateTests(unittest.TestCase):
    def test_allowlist_excludes_runtime_cache_and_builder_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            frontend = root / "frontend"
            (runtime / "packages" / "app" / "__pycache__").mkdir(parents=True)
            (runtime / "packages" / "bin").mkdir()
            frontend.mkdir()
            (runtime / "python.exe").write_bytes(b"synthetic")
            (runtime / "packages" / "app" / "module.py").write_text("x = 1")
            (runtime / "packages" / "app" / "__pycache__" / "module.pyc").write_bytes(b"cache")
            (runtime / "packages" / "bin" / "builder.exe").write_bytes(b"builder")
            (frontend / "index.html").write_text("<html></html>")
            config = root / "bootstrap.example.yaml"
            config.write_text("bind_host: 127.0.0.1")
            names = [name for _, name in MODULE._source_files(runtime, frontend, config)]
            self.assertEqual(names, [
                "payload/config/bootstrap.example.yaml",
                "payload/frontend/dist/index.html",
                "payload/runtime/packages/app/module.py",
                "payload/runtime/python.exe",
            ])

    def test_private_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            runtime.mkdir()
            (runtime / "private.key").write_text("synthetic")
            frontend = root / "frontend"
            frontend.mkdir()
            config = root / "bootstrap.example.yaml"
            config.write_text("synthetic")
            with self.assertRaisesRegex(ValueError, "private file"):
                MODULE._source_files(runtime, frontend, config)

    def test_inventory_never_claims_license_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            packages = Path(temp)
            dist = packages / "synthetic-1.0.dist-info"
            dist.mkdir()
            (dist / "METADATA").write_text("Name: synthetic\nVersion: 1.0\nLicense-Expression: MIT\n")
            (dist / "LICENSE.txt").write_text("synthetic")
            inventory = MODULE._license_inventory(packages)
            self.assertEqual(inventory["distribution_count"], 1)
            self.assertEqual(inventory["status"], "REVIEW_REQUIRED")
            self.assertEqual(inventory["distributions"][0]["review_status"], "REVIEW_REQUIRED")

    def test_archive_digest_verifier_rejects_tamper_and_extra(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "candidate.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("payload/runtime/python.exe", b"synthetic")
            expected = {"payload/runtime/python.exe": MODULE.hashlib.sha256(b"synthetic").hexdigest()}
            MODULE._verify_archive(archive, expected)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                MODULE._verify_archive(archive, {"payload/runtime/python.exe": "0" * 64})
            with self.assertRaisesRegex(ValueError, "inventory mismatch"):
                MODULE._verify_archive(archive, {})

    def test_reinstall_preflight_rejects_traversal_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape", b"synthetic")
            with self.assertRaisesRegex(ValueError, "path rejected"):
                VERIFY.inspect_archive(archive)

    def test_reinstall_preflight_rejects_release_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("manifest.json", '{"kind":"WINDOWS11_EMBEDDED_DEVELOPMENT_CANDIDATE","release_eligible":true}')
                bundle.writestr("third-party-inventory.json", '{"status":"REVIEW_REQUIRED","distribution_count":93}')
                bundle.writestr("payload-sha256sums.txt", b"")
            with self.assertRaisesRegex(ValueError, "release or license gate rejected"):
                VERIFY.inspect_archive(archive)


if __name__ == "__main__":
    unittest.main()
