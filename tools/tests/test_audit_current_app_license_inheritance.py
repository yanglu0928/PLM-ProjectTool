from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_current_app_license_inheritance import audit  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CurrentLicenseInheritanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name) / "parent.zip"
        self.current = Path(self.temp.name) / "current.zip"
        self.mapping = "payload/third-party-licenses/native-ocr/review-map.json"
        self.text = "payload/third-party-licenses/native-ocr/texts/demo.txt"
        self.inventory = json.dumps({
            "review_status": "REVIEW_REQUIRED",
            "base": {"unified": {"distribution_count": 2, "distributions": [
                {"name": "plm-project-tool-backend", "review_status": "REVIEW_REQUIRED"},
                {"name": "external", "review_status": "REVIEW_REQUIRED"},
            ]}},
            "native_ocr_license_evidence": {
                "mapping_path": self.mapping, "legal_clearance": False,
                "review_status": "REVIEW_REQUIRED", "evidence_record_count": 1,
                "unique_text_count": 1,
            },
        }).encode()
        self.retained = {
            self.mapping: json.dumps({"evidence": [{"text_path": self.text,
                                                     "text_sha256": sha(b"license")}] }).encode(),
            self.text: b"license",
            "payload/runtime/packages/external-1.dist-info/METADATA": b"external",
        }
        self._write(self.parent, {
            **self.retained,
            "payload/runtime/packages/plm_assistant/__init__.py": b"old",
            "payload/runtime/packages/plm_project_tool_backend-0.1.0.dev0.dist-info/METADATA":
                b"Version: 0.1.0.dev0\nRequires-Dist: external==1\n",
        }, parent_sha=None)
        self.parent_sha = sha(self.parent.read_bytes())
        self._write(self.current, {
            **self.retained,
            "payload/runtime/packages/plm_assistant/__init__.py": b"new",
            "payload/runtime/packages/plm_project_tool_backend-0.1.0.dev0.dist-info/METADATA":
                b"Version: 0.1.0.dev0\nRequires-Dist: external==1\n",
        }, parent_sha=self.parent_sha)

    def _write(self, path: Path, payload: dict[str, bytes], *, parent_sha: str | None) -> None:
        manifest = {"payload_file_count": len(payload), "release_eligible": False,
                    "legal_clearance": False, "formal_tls_material_included": False}
        if parent_sha:
            manifest.update({"kind": "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE",
                             "parent_candidate_sha256": parent_sha,
                             "source_git_commit": "a" * 40})
        with zipfile.ZipFile(path, "w") as output:
            for name, data in payload.items():
                output.writestr(name, data)
            output.writestr("payload-sha256sums.txt", "".join(
                f"{sha(data)}  {name}\n" for name, data in sorted(payload.items())))
            output.writestr("third-party-inventory.json", self.inventory)
            output.writestr("manifest.json", json.dumps(manifest))

    def test_retained_bytes_and_open_legal_boundary(self) -> None:
        result = audit(self.parent, self.current, parent_sha=self.parent_sha,
                       current_sha=sha(self.current.read_bytes()))
        self.assertEqual(result["retained_non_app_file_count"], 3)
        self.assertEqual(result["third_party_python_distribution_count"], 1)
        self.assertEqual(result["backend_declared_requirement_count"], 1)
        self.assertFalse(result["legal_clearance"])

    def test_changed_third_party_and_wrong_archive_digest_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity differs"):
            audit(self.parent, self.current, parent_sha=self.parent_sha,
                  current_sha="0" * 64)
        changed = {**self.retained, self.text: b"changed"}
        self._write(self.current, {
            **changed, "payload/runtime/packages/plm_assistant/__init__.py": b"new",
            "payload/runtime/packages/plm_project_tool_backend-0.1.0.dev0.dist-info/METADATA":
                b"Version: 0.1.0.dev0\nRequires-Dist: external==1\n",
        }, parent_sha=self.parent_sha)
        with self.assertRaisesRegex(ValueError, "third-party/runtime payload changed"):
            audit(self.parent, self.current, parent_sha=self.parent_sha,
                  current_sha=sha(self.current.read_bytes()))


if __name__ == "__main__":
    unittest.main()
