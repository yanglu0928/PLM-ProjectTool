from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_windows_paddle_model_bundle as bundle


class OfflinePaddleModelBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dirs = {}
        self.models = {}
        contents = {}
        for role in ("det", "rec"):
            directory = self.root / role
            directory.mkdir()
            self.dirs[role] = directory
            revision = role * 40
            objects = {}
            for name in bundle.FILES:
                data = (b"---\nlicense: apache-2.0\n---\n" if name == "README.md"
                        else (role + name).encode("ascii"))
                (directory / name).write_bytes(data)
                objects[name] = bundle._object_id(data, name == "inference.pdiparams")
                contents[bundle._entry(role, name)] = data
                if name != "README.md":
                    metadata = directory / ".cache" / "huggingface" / "download"
                    metadata.mkdir(parents=True, exist_ok=True)
                    (metadata / f"{name}.metadata").write_text(
                        f"{revision}\n{objects[name]}\n", encoding="utf-8")
            self.models[role] = {"revision": revision, "objects": objects}
        self.fingerprint = bundle._fingerprint(contents)
        self.patches = [patch("audit_paddle_model_revisions.MODELS", self.models),
                        patch.object(bundle, "EXPECTED_FINGERPRINT", self.fingerprint)]
        for active in self.patches:
            active.start()
            self.addCleanup(active.stop)

    def test_deterministic_bundle_and_fail_closed_rebuild(self) -> None:
        first = self.root / "one.zip"
        second = self.root / "two.zip"
        result = bundle.build(self.dirs["det"], self.dirs["rec"], first)
        self.assertEqual(result["file_count"], 10)
        self.assertFalse(result["release_eligible"])
        self.assertEqual(result["archive_sha256"], bundle.build(
            self.dirs["det"], self.dirs["rec"], second)["archive_sha256"])
        with self.assertRaisesRegex(ValueError, "already exists"):
            bundle.build(self.dirs["det"], self.dirs["rec"], first)
        self.assertEqual(result["archive_sha256"], bundle.verify(first)["archive_sha256"])

    def test_rejects_changed_upstream_bytes_and_archive_path(self) -> None:
        valid = self.root / "valid.zip"
        bundle.build(self.dirs["det"], self.dirs["rec"], valid)
        malicious = self.root / "malicious.zip"
        with zipfile.ZipFile(valid) as source, zipfile.ZipFile(malicious, "x") as dest:
            for name in source.namelist():
                dest.writestr(name, source.read(name))
            dest.writestr("../escape.txt", b"bad")
        with self.assertRaisesRegex(ValueError, "path rejected"):
            bundle.verify(malicious)
        (self.dirs["rec"] / "inference.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "object mismatch"):
            bundle.build(self.dirs["det"], self.dirs["rec"], self.root / "changed.zip")
        self.assertFalse((self.root / "changed.zip").exists())

    def test_rejects_manifest_claim_even_with_valid_payload(self) -> None:
        valid = self.root / "valid.zip"
        bundle.build(self.dirs["det"], self.dirs["rec"], valid)
        changed = self.root / "changed.zip"
        with zipfile.ZipFile(valid) as source, zipfile.ZipFile(changed, "x") as dest:
            for name in source.namelist():
                data = source.read(name)
                if name == "manifest.json":
                    manifest = json.loads(data)
                    manifest["release_eligible"] = True
                    data = json.dumps(manifest).encode("utf-8")
                dest.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "manifest rejected"):
            bundle.verify(changed)


if __name__ == "__main__":
    unittest.main()
