from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_tesseract_runtime_dependencies import audit, pe_imports


def minimal_amd64_pe(import_name: str | None) -> bytes:
    data = bytearray(0x400)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    struct.pack_into("<H", data, 0x86, 1)
    struct.pack_into("<H", data, 0x94, 0xF0)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 108, 16)
    section = optional + 0xF0
    struct.pack_into("<IIII", data, section + 8, 0x200, 0x1000, 0x200, 0x200)
    if import_name:
        struct.pack_into("<II", data, optional + 120, 0x1000, 40)
        struct.pack_into("<IIIII", data, 0x200, 0, 0, 0, 0x1050, 0)
        data[0x250:0x250 + len(import_name) + 1] = import_name.encode("ascii") + b"\0"
    return bytes(data)


class TesseractPeImportTests(unittest.TestCase):
    def test_recursive_local_imports_and_external_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "tesseract.exe").write_bytes(minimal_amd64_pe("LOCAL.dll"))
            (root / "local.dll").write_bytes(minimal_amd64_pe("KERNEL32.dll"))
            (root / "unused.dll").write_bytes(minimal_amd64_pe(None))
            result = audit(root)
            self.assertEqual(result["needed_local_files"], ["local.dll", "tesseract.exe"])
            self.assertEqual(result["unused_local_dlls"], ["unused.dll"])
            self.assertEqual(result["external_import_names"], ["kernel32.dll"])
            self.assertFalse(result["release_eligible"])

    def test_bad_pe_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.exe"
            path.write_bytes(b"not a PE")
            with self.assertRaisesRegex(ValueError, "not a PE"):
                pe_imports(path)


if __name__ == "__main__":
    unittest.main()
