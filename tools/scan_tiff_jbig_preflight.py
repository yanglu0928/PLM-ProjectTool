"""Read-only TIFF metadata preflight for the no-JBIG runtime candidate.

Unsupported or malformed input blocks upgrade; the CLI never emits file paths.
This is not yet wired into a production installer.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import BinaryIO


JBIG_COMPRESSION = 34661  # libtiff 4.7.2 tiff.h: COMPRESSION_JBIG
MAX_DIRECTORIES = 10000
MAX_ENTRIES = 100000
MAX_SUBIFDS = 10000


class UnsupportedTiff(ValueError):
    pass


def read_at(stream: BinaryIO, size: int, offset: int, length: int) -> bytes:
    if offset < 0 or length < 0 or offset > size or length > size - offset:
        raise UnsupportedTiff("metadata offset outside TIFF")
    stream.seek(offset)
    result = stream.read(length)
    if len(result) != length:
        raise UnsupportedTiff("short TIFF read")
    return result


def inspect(path: Path) -> bool:
    """Return True if an image IFD uses ISO JBIG; reject unreadable metadata."""
    with path.open("rb") as stream:
        return inspect_stream(stream)


def inspect_stream(stream: BinaryIO) -> bool:
    """Inspect an already verified, seekable private byte snapshot."""
    original = stream.tell()
    try:
        stream.seek(0, 2)
        size = stream.tell()
        header = read_at(stream, size, 0, 8)
        if header[:2] not in (b"II", b"MM"):
            raise UnsupportedTiff("not a TIFF byte order")
        endian = "<" if header[:2] == b"II" else ">"
        magic = struct.unpack_from(endian + "H", header, 2)[0]
        if magic == 42:
            big = False
            first = struct.unpack_from(endian + "I", header, 4)[0]
            count_size, entry_size, inline_size, offset_size = 2, 12, 4, 4
        elif magic == 43:
            big = True
            extra = read_at(stream, size, 8, 8)
            if struct.unpack_from(endian + "HH", header, 4) != (8, 0):
                raise UnsupportedTiff("unsupported BigTIFF offset size")
            first = struct.unpack(endian + "Q", extra)[0]
            count_size, entry_size, inline_size, offset_size = 8, 20, 8, 8
        else:
            raise UnsupportedTiff("unsupported TIFF magic")
        if first == 0:
            raise UnsupportedTiff("TIFF has no image directory")
        queue = [first]
        visited: set[int] = set()
        while queue:
            offset = queue.pop()
            if offset in visited or len(visited) >= MAX_DIRECTORIES:
                raise UnsupportedTiff("TIFF directory cycle or limit")
            visited.add(offset)
            raw_count = read_at(stream, size, offset, count_size)
            count = struct.unpack(endian + ("Q" if big else "H"), raw_count)[0]
            if count > MAX_ENTRIES:
                raise UnsupportedTiff("too many TIFF tags")
            entries_start = offset + count_size
            end = entries_start + count * entry_size
            next_raw = read_at(stream, size, end, offset_size)
            next_offset = struct.unpack(endian + ("Q" if big else "I"), next_raw)[0]
            if next_offset:
                queue.append(next_offset)
            for index in range(count):
                entry = read_at(stream, size, entries_start + index * entry_size, entry_size)
                tag, kind = struct.unpack_from(endian + "HH", entry)
                if tag not in (259, 330):
                    continue
                value_count = struct.unpack_from(endian + ("Q" if big else "I"), entry, 4)[0]
                if tag == 259:
                    if kind != 3 or value_count != 1:
                        raise UnsupportedTiff("unsupported compression tag")
                    compression = struct.unpack_from(endian + "H", entry, entry_size - inline_size)[0]
                    if compression == JBIG_COMPRESSION:
                        return True
                    continue
                if kind not in (4, 13, 16, 18) or value_count > MAX_SUBIFDS:
                    raise UnsupportedTiff("unsupported SubIFD tag")
                width = 4 if kind in (4, 13) else 8
                total = width * value_count
                value_start = entry_size - inline_size
                if total <= inline_size:
                    data = entry[value_start:value_start + total]
                else:
                    location = struct.unpack_from(endian + ("Q" if big else "I"), entry, value_start)[0]
                    data = read_at(stream, size, location, total)
                for position in range(value_count):
                    sub = struct.unpack_from(endian + ("I" if width == 4 else "Q"), data,
                                             position * width)[0]
                    if sub:
                        queue.append(sub)
        return False
    finally:
        stream.seek(original)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", type=Path, required=True)
    args = parser.parse_args()
    count_jbig = count_clear = count_unknown = 0
    for path in args.file:
        try:
            result = inspect(path)
        except (OSError, UnsupportedTiff, struct.error):
            count_unknown += 1
        else:
            if result:
                count_jbig += 1
            else:
                count_clear += 1
    status = "BLOCK_JBIG" if count_jbig else "BLOCK_UNKNOWN" if count_unknown else "CLEAR"
    print(json.dumps({"status": status, "files": len(args.file), "jbig": count_jbig,
                      "clear": count_clear, "unknown": count_unknown,
                      "upgrade_allowed": status == "CLEAR"}))
    return 0 if status == "CLEAR" else 2


if __name__ == "__main__":
    raise SystemExit(main())
