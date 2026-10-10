from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ghostscript_portable_payload import audit


class GhostscriptPortableAuditTests(unittest.TestCase):
    def test_independent_extraction_and_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / "payload"
            (payload / "bin").mkdir(parents=True)
            (payload / "doc").mkdir()
            (payload / "bin" / "gswin64c.exe").write_bytes(b"test executable")
            (payload / "doc" / "COPYING").write_bytes(b"test license")
            installer = root / "installer.exe"
            installer.write_bytes(b"test archive")
            pristine = root / "pristine"
            shutil.copytree(payload, pristine)

            def process(command: list[str], **_kwargs: object):
                if command[1] == "x":
                    destination = Path(command[3][2:])
                    shutil.copytree(pristine, destination, dirs_exist_ok=True)
                    return type("Result", (), {"returncode": 0})()
                return type("Result", (), {"returncode": 0, "stdout": "10.08.0\n"})()

            args = {
                "installer_sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
                "exe_sha256": hashlib.sha256((payload / "bin" / "gswin64c.exe").read_bytes()).hexdigest(),
                "copying_sha256": hashlib.sha256((payload / "doc" / "COPYING").read_bytes()).hexdigest(),
                "expected_count": 2,
            }
            with patch("audit_ghostscript_portable_payload.subprocess.run", side_effect=process):
                result = audit(installer, payload, root / "7z.exe", **args)
                self.assertEqual(result["file_count"], 2)
                self.assertEqual(result["notice_paths"], ["doc/COPYING"])
                self.assertFalse(result["release_eligible"])
                (payload / "bin" / "gswin64c.exe").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "CLI hash mismatch"):
                    audit(installer, payload, root / "7z.exe", **args)
                shutil.copy2(pristine / "bin" / "gswin64c.exe", payload / "bin" / "gswin64c.exe")
                (payload / "bin" / "extra.dll").write_bytes(b"extra")
                with self.assertRaisesRegex(ValueError, "count mismatch"):
                    audit(installer, payload, root / "7z.exe", **args)


if __name__ == "__main__":
    unittest.main()
