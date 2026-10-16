from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("native_source_audit", TOOLS / "audit_windows_candidate_native_sources.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NativeSourceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        candidate = root / "candidate.zip"
        with zipfile.ZipFile(candidate, "w") as archive:
            archive.writestr("payload/runtime/python.exe", b"python binary")
            archive.writestr("payload/runtime/packages/shared.dll", b"shared native")
        python_zip = root / "python-3.13.15-embed-amd64.zip"
        with zipfile.ZipFile(python_zip, "w") as archive:
            archive.writestr("python.exe", b"python binary")
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        lines = []
        for index in range(93):
            wheel = wheelhouse / f"synthetic_{index}-1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                if index == 0:
                    archive.writestr("synthetic.libs/shared.dll", b"shared native")
                if index == 1:
                    archive.writestr("synthetic_1-1.0.data/platlib/shared.dll", b"shared native")
            lines.append(f"{MODULE.digest_file(wheel)}  {wheel.name}\n")
        hashes = root / "sha256sums.txt"
        hashes.write_text("".join(lines), encoding="ascii")
        return candidate, python_zip, wheelhouse, hashes

    def test_official_and_wheel_platlib_byte_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, python_zip, wheelhouse, hashes = self._fixture(Path(temp))
            with patch.object(MODULE, "PYTHON_SHA256", MODULE.digest_file(python_zip)), patch.object(
                MODULE, "inspect_archive", return_value=({"release_eligible": False}, {}, {})
            ):
                result = MODULE.audit_native(candidate, python_zip, wheelhouse, hashes)
            self.assertEqual(result["status"], "SOURCE_MATCH_PASS")
            self.assertEqual(result["source_kind_counts"], {"OFFICIAL_PYTHON_EMBED": 1, "PINNED_WHEEL": 1})
            wheel_entry = next(item for item in result["entries"] if item["candidate_path"].endswith("shared.dll"))
            self.assertEqual(wheel_entry["possible_source_count"], 2)
            self.assertIn(".data/platlib/", wheel_entry["source"]["source_member"])
            self.assertFalse(result["release_eligible"])

    def test_tampered_wheel_source_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, python_zip, wheelhouse, hashes = self._fixture(Path(temp))
            (wheelhouse / "synthetic_0-1.0-py3-none-any.whl").write_bytes(b"tampered")
            with patch.object(MODULE, "PYTHON_SHA256", MODULE.digest_file(python_zip)), patch.object(
                MODULE, "inspect_archive", return_value=({"release_eligible": False}, {}, {})
            ), self.assertRaisesRegex(ValueError, "wheel source hash mismatch"):
                MODULE.audit_native(candidate, python_zip, wheelhouse, hashes)

    def test_unmatched_native_file_remains_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate, python_zip, wheelhouse, hashes = self._fixture(Path(temp))
            with zipfile.ZipFile(candidate, "a") as archive:
                archive.writestr("payload/runtime/packages/unknown.pyd", b"unknown binary")
            with patch.object(MODULE, "PYTHON_SHA256", MODULE.digest_file(python_zip)), patch.object(
                MODULE, "inspect_archive", return_value=({"release_eligible": False}, {}, {})
            ):
                result = MODULE.audit_native(candidate, python_zip, wheelhouse, hashes)
            self.assertEqual(result["status"], "SOURCE_MATCH_INCOMPLETE")
            self.assertEqual(result["unresolved_count"], 1)


if __name__ == "__main__":
    unittest.main()
