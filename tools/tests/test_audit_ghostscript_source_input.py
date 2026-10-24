from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_ghostscript_source_input import audit, inspect_source  # noqa: E402


class GhostscriptSourceInputTests(unittest.TestCase):
    def _source(self, path: Path, *, bad_path: bool = False) -> tuple[str, str, tuple[str, ...]]:
        root = "ghostscript-10.08.0"
        files = {f"{root}/doc/COPYING": b"synthetic AGPL fixture",
                 f"{root}/LICENSE": b"synthetic license fixture",
                 f"{root}/README": b"synthetic readme fixture",
                 f"{root}/Makefile.in": b"synthetic make fixture",
                 f"{root}/psi/msvc.mak": b"synthetic Windows build fixture",
                 f"{root}/windows/ghostscript.vcxproj": b"synthetic project fixture"}
        if bad_path:
            files[f"{root}/../escape"] = b"bad path"
        with tarfile.open(path, "w:xz") as archive:
            for name, body in files.items():
                item = tarfile.TarInfo(name)
                item.size = len(body)
                archive.addfile(item, io.BytesIO(body))
        return (hashlib.sha256(path.read_bytes()).hexdigest(),
                hashlib.sha256(files[f"{root}/doc/COPYING"]).hexdigest(),
                tuple(files))

    def test_full_fixture_requires_matching_bytes_members_and_copying(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.tar.xz"
            source_hash, copying_hash, required = self._source(source)
            result = inspect_source(source, expected_sha256=source_hash,
                                    expected_bytes=source.stat().st_size,
                                    expected_members=6, expected_files=6,
                                    expected_copying=copying_hash, required=required)
            self.assertEqual(result["regular_files"], 6)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                inspect_source(source, expected_sha256="0" * 64,
                               expected_bytes=source.stat().st_size)

    def test_traversal_member_rejected_even_with_valid_archive_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.tar.xz"
            source_hash, copying_hash, required = self._source(source, bad_path=True)
            with self.assertRaisesRegex(ValueError, "path rejected"):
                inspect_source(source, expected_sha256=source_hash,
                               expected_bytes=source.stat().st_size,
                               expected_members=7, expected_files=7,
                               expected_copying=copying_hash, required=required[:6])

    def test_bad_fixed_candidate_rejected_before_source(self) -> None:
        with patch("audit_ghostscript_source_input.verify", side_effect=ValueError("bad candidate")):
            with patch("audit_ghostscript_source_input.inspect_source") as source:
                with self.assertRaisesRegex(ValueError, "bad candidate"):
                    audit(Path("missing.zip"), Path("missing-parent.zip"), Path("missing.tar.xz"))
                source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
