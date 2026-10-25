from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_pe_rebuild_equivalence import normalized


def fixture(coff_time: int, checksum: int, export_time: int, payload: int = 7) -> bytes:
    data = bytearray(1024)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    struct.pack_into("<H", data, 0x86, 1)
    struct.pack_into("<I", data, 0x88, coff_time)
    struct.pack_into("<H", data, 0x94, 240)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<I", data, optional + 64, checksum)
    struct.pack_into("<II", data, optional + 112, 0x1000, 40)
    section = optional + 240
    struct.pack_into("<IIII", data, section + 8, 512, 0x1000, 512, 512)
    struct.pack_into("<I", data, 516, export_time)
    data[800] = payload
    return bytes(data)


class PeRebuildEquivalenceTests(unittest.TestCase):
    def test_only_three_pe_metadata_fields_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.dll"
            second = Path(temporary) / "second.dll"
            first.write_bytes(fixture(1, 2, 3))
            second.write_bytes(fixture(4, 5, 6))
            one = normalized(first)
            two = normalized(second)
            self.assertNotEqual(one[0], two[0])
            self.assertEqual(one[1], two[1])
            self.assertEqual(one[2], (0x88, 0x98 + 64, 516))
            second.write_bytes(fixture(4, 5, 6, payload=8))
            self.assertNotEqual(one[1], normalized(second)[1])

    def test_bad_and_truncated_inputs_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.dll"
            for data in (b"", b"MZ", fixture(1, 2, 3)[:150]):
                sample.write_bytes(data)
                with self.assertRaises(ValueError):
                    normalized(sample)


if __name__ == "__main__":
    unittest.main()
