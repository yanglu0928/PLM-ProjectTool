from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scan_tiff_jbig_preflight import UnsupportedTiff, inspect


def classic(compression: int, endian: str = "<", second: int | None = None,
            subifd: int | None = None) -> bytes:
    data = bytearray(128)
    data[:2] = b"II" if endian == "<" else b"MM"
    struct.pack_into(endian + "HI", data, 2, 42, 8)
    entries = 2 if subifd is not None else 1
    struct.pack_into(endian + "H", data, 8, entries)
    struct.pack_into(endian + "HHI", data, 10, 259, 3, 1)
    struct.pack_into(endian + "H", data, 18, compression)
    if subifd is not None:
        struct.pack_into(endian + "HHII", data, 22, 330, 4, 1, 64)
    struct.pack_into(endian + "I", data, 10 + entries * 12, 64 if second is not None else 0)
    if second is not None or subifd is not None:
        struct.pack_into(endian + "H", data, 64, 1)
        struct.pack_into(endian + "HHI", data, 66, 259, 3, 1)
        struct.pack_into(endian + "H", data, 74,
                         second if second is not None else subifd)
    return bytes(data)


def bigtiff(compression: int, endian: str = "<") -> bytes:
    data = bytearray(128)
    data[:2] = b"II" if endian == "<" else b"MM"
    struct.pack_into(endian + "HHHQ", data, 2, 43, 8, 0, 16)
    struct.pack_into(endian + "Q", data, 16, 1)
    struct.pack_into(endian + "HHQ", data, 24, 259, 3, 1)
    struct.pack_into(endian + "H", data, 36, compression)
    return bytes(data)


class TiffJbigPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "input.tif"

    def scan(self, data: bytes) -> bool:
        self.path.write_bytes(data)
        return inspect(self.path)

    def test_both_endian_and_bigtiff(self) -> None:
        for endian in ("<", ">"):
            self.assertTrue(self.scan(classic(34661, endian)))
            self.assertFalse(self.scan(classic(1, endian)))
            self.assertTrue(self.scan(bigtiff(34661, endian)))
            self.assertFalse(self.scan(bigtiff(1, endian)))

    def test_later_page_and_subifd(self) -> None:
        self.assertTrue(self.scan(classic(1, second=34661)))
        self.assertTrue(self.scan(classic(1, subifd=34661)))

    def test_malformed_and_cycle_fail_closed(self) -> None:
        for sample in (b"", b"not TIFF", classic(1)[:12]):
            with self.assertRaises(UnsupportedTiff):
                self.scan(sample)
        cycle = bytearray(classic(1))
        struct.pack_into("<I", cycle, 22, 8)
        with self.assertRaises(UnsupportedTiff):
            self.scan(bytes(cycle))


if __name__ == "__main__":
    unittest.main()
