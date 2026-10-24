"""Compare two AMD64 PE DLLs after masking only documented build timestamps/checksum.

This is evidence about bytes, not a proof of reproducible release inputs or behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


def normalized(path: Path) -> tuple[str, str, tuple[int, int, int]]:
    data = bytearray(path.read_bytes())
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("not a PE file")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data):
        raise ValueError("truncated PE header")
    if data[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", data, pe + 4)[0] != 0x8664:
        raise ValueError("not an AMD64 PE file")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    optional = pe + 24
    if optional_size < 224 or optional + optional_size + count * 40 > len(data):
        raise ValueError("PE sections or optional header truncated")
    if struct.unpack_from("<H", data, optional)[0] != 0x20B:
        raise ValueError("PE32+ optional header missing")
    export_rva, export_size = struct.unpack_from("<II", data, optional + 112)
    if not export_rva or export_size < 40:
        raise ValueError("export directory missing")
    export_offset = None
    for index in range(count):
        section = optional + optional_size + index * 40
        _, rva, raw_size, pointer = struct.unpack_from("<IIII", data, section + 8)
        if rva <= export_rva and export_rva + 40 <= rva + raw_size and pointer + raw_size <= len(data):
            export_offset = pointer + export_rva - rva
            break
    if export_offset is None or export_offset + 40 > len(data):
        raise ValueError("export directory outside file")
    raw = hashlib.sha256(data).hexdigest()
    spans = (pe + 8, optional + 64, export_offset + 4)
    for position in spans:
        data[position:position + 4] = b"\0" * 4
    return raw, hashlib.sha256(data).hexdigest(), spans


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    args = parser.parse_args()
    first = normalized(args.first)
    second = normalized(args.second)
    if first[2] != second[2]:
        raise ValueError("PE structure differs")
    result = {"raw_sha256": [first[0], second[0]],
              "masked_offsets": first[2],
              "normalized_sha256": [first[1], second[1]],
              "equal_after_pe_metadata_mask": first[1] == second[1],
              "limitation": "Only PE COFF/export timestamps and optional checksum are masked"}
    print(json.dumps(result))
    return 0 if result["equal_after_pe_metadata_mask"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
