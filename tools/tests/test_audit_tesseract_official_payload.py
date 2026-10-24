from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_tesseract_official_payload import audit, digest


class OfficialPayloadAuditTests(unittest.TestCase):
    def test_inventory_never_clears_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installer = root / "installer.exe"
            installer.write_bytes(b"installer")
            payload = root / "payload"
            (payload / "doc").mkdir(parents=True)
            (payload / "tesseract.exe").write_bytes(b"exe")
            (payload / "library.dll").write_bytes(b"dll")
            (payload / "doc" / "LICENSE").write_bytes(b"Apache License")
            with zipfile.ZipFile(payload / "library.jar", "w") as archive:
                archive.writestr("META-INF/LICENSE.txt", "license")
            options = {"installer_sha256": digest(installer),
                       "exe_sha256": digest(payload / "tesseract.exe"),
                       "license_sha256": digest(payload / "doc" / "LICENSE"),
                       "expected_counts": (4, 1, 1)}
            canonical = root / "canonical"
            shutil.copytree(payload, canonical)
            def extract(args, **kwargs):
                destination = Path(next(value[2:] for value in args if value.startswith("-o")))
                shutil.copytree(canonical, destination, dirs_exist_ok=True)
                return type("Result", (), {"returncode": 0})()

            with patch("audit_tesseract_official_payload.subprocess.run", side_effect=extract):
                result = audit(installer, payload, root / "7z.exe", **options)
            self.assertFalse(result["release_eligible"])
            self.assertEqual(result["standalone_notice_files"], ["doc/LICENSE"])
            self.assertEqual(result["jar_embedded_notice_files"]["library.jar"], ["META-INF/LICENSE.txt"])
            (payload / "library.dll").write_bytes(b"tampered")
            recorded = {item["path"]: item["sha256"] for item in result["files"]}
            self.assertNotEqual(recorded["library.dll"], digest(payload / "library.dll"))
            with patch("audit_tesseract_official_payload.subprocess.run", side_effect=extract):
                with self.assertRaisesRegex(ValueError, "extracted file mismatch"):
                    audit(installer, payload, root / "7z.exe", **options)
            (payload / "extra.dll").write_bytes(b"unexpected")
            with self.assertRaisesRegex(ValueError, "count mismatch"):
                audit(installer, payload, root / "7z.exe", **options)
            installer.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "installer hash mismatch"):
                audit(installer, payload, root / "7z.exe", **options)


if __name__ == "__main__":
    unittest.main()
