from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "frontend_license_audit", Path(__file__).resolve().parents[1] / "audit_frontend_bundle_licenses.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendLicenseAuditTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        app = root / "offline-source" / "apps" / "frontend"
        frozen = app / "dist"
        audit = app / "dist-license-audit"
        (frozen / "assets").mkdir(parents=True)
        (audit / "assets").mkdir(parents=True)
        files = {"index.html": b"html", "assets/index-x.js": b"bundle", "assets/index-y.css": b"css"}
        for name, data in files.items():
            (frozen / name).write_bytes(data)
            (audit / name).write_bytes(data + b"\n//# sourceMappingURL=index-x.js.map" if name.endswith(".js") else data)
        package = app / "node_modules" / ".pnpm" / "example@1.0" / "node_modules" / "example"
        package.mkdir(parents=True)
        (package / "index.js").write_text("export const x = 1", encoding="utf-8")
        (package / "package.json").write_text(json.dumps({"name": "example", "version": "1.0", "license": "MIT"}), encoding="utf-8")
        (package / "LICENSE").write_text("synthetic", encoding="utf-8")
        direct = app / "node_modules" / "facade"
        direct.mkdir()
        (direct / "package.json").write_text(json.dumps({"name": "facade", "version": "2.0", "license": "MIT"}), encoding="utf-8")
        (direct / "LICENSE").write_text("facade notice", encoding="utf-8")
        (app / "package.json").write_text(json.dumps({"dependencies": {"facade": "2.0"}}), encoding="utf-8")
        (app / "pnpm-lock.yaml").write_bytes(b"synthetic lock")
        (audit / "assets" / "index-x.js.map").write_text(json.dumps({
            "sources": ["../../node_modules/.pnpm/example@1.0/node_modules/example/index.js"],
            "sourcesContent": ["export const x = 1"],
        }), encoding="utf-8")
        (root / "summary.json").write_text(json.dumps({
            "status": "WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS", "dist_file_count": 3,
            "source_commit": "synthetic", "lock_sha256": MODULE.sha256(b"synthetic lock"),
        }), encoding="utf-8")
        (root / "dist-sha256sums.txt").write_text("".join(
            f"{MODULE.sha256(data)}  {name}\n" for name, data in files.items()
        ), encoding="ascii")
        return app

    def test_exact_bundle_source_and_license_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            result = MODULE.audit_frontend(root)
            self.assertEqual(result["mapped_package_count"], 1)
            self.assertEqual(result["packages"][0]["license_files"][0]["sha256"], MODULE.sha256(b"synthetic"))
            self.assertFalse(result["direct_dependencies"][0]["mapped_into_bundle"])
            self.assertFalse(result["release_eligible"])

    def test_divergent_bundle_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self._fixture(root)
            (app / "dist-license-audit" / "assets" / "index-x.js").write_bytes(b"different")
            with self.assertRaisesRegex(ValueError, "audit JS differs"):
                MODULE.audit_frontend(root)

    def test_divergent_mapped_source_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = self._fixture(root)
            (app / "node_modules" / ".pnpm" / "example@1.0" / "node_modules" / "example" / "index.js").write_text("changed")
            with self.assertRaisesRegex(ValueError, "package content mismatch"):
                MODULE.audit_frontend(root)


if __name__ == "__main__":
    unittest.main()
