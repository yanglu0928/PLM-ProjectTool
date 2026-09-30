"""Read PE import tables to bound a candidate Tesseract CLI runtime subset.

Static imports do not capture LoadLibrary/delay behavior or prove license rights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _name(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        raise ValueError("PE import name outside file")
    end = data.find(b"\0", offset, min(offset + 256, len(data)))
    if end < 0:
        raise ValueError("PE import name unterminated")
    try:
        result = data[offset:end].decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("PE import name non-ASCII") from error
    if not result or "/" in result or "\\" in result or ":" in result:
        raise ValueError("PE import name invalid")
    return result.casefold()


def pe_imports(path: Path) -> set[str]:
    data = path.read_bytes()
    try:
        if data[:2] != b"MZ":
            raise ValueError("not a PE file")
        pe = _u32(data, 0x3C)
        if data[pe:pe + 4] != b"PE\0\0" or _u16(data, pe + 4) != 0x8664:
            raise ValueError("not an AMD64 PE file")
        sections = _u16(data, pe + 6)
        optional_size = _u16(data, pe + 20)
        optional = pe + 24
        if _u16(data, optional) != 0x20B or sections < 1 or sections > 96 or optional_size < 128:
            raise ValueError("PE optional header rejected")
        section_start = optional + optional_size
        maps = []
        for index in range(sections):
            start = section_start + index * 40
            virtual_size, rva, raw_size, raw_pointer = struct.unpack_from("<IIII", data, start + 8)
            maps.append((rva, max(virtual_size, raw_size), raw_pointer, raw_size))

        def offset(rva: int, length: int = 1) -> int:
            for base, virtual_size, raw_pointer, raw_size in maps:
                if base <= rva and rva + length <= base + min(virtual_size, raw_size):
                    result = raw_pointer + rva - base
                    if result + length <= len(data):
                        return result
            raise ValueError("PE import RVA outside file")

        directory_count = _u32(data, optional + 108)
        if directory_count < 2:
            return set()
        import_rva, import_size = struct.unpack_from("<II", data, optional + 120)
        result = set()
        if import_rva and import_size:
            start = offset(import_rva, 20)
            for index in range(min(import_size // 20, 4096)):
                descriptor = start + index * 20
                if descriptor + 20 > len(data):
                    raise ValueError("PE import descriptor outside file")
                values = struct.unpack_from("<IIIII", data, descriptor)
                if not any(values):
                    break
                result.add(_name(data, offset(values[3])))
            else:
                raise ValueError("PE import descriptor terminator missing")
        return result
    except struct.error as error:
        raise ValueError("PE file truncated") from error


def audit(root: Path) -> dict:
    files = {path.name.casefold(): path for path in root.iterdir()
             if path.is_file() and path.suffix.casefold() in (".dll", ".exe")}
    if "tesseract.exe" not in files or len(files) != len([
        path for path in root.iterdir() if path.is_file() and path.suffix.casefold() in (".dll", ".exe")]):
        raise ValueError("Tesseract root executable or case-insensitive uniqueness missing")
    needed = {"tesseract.exe"}
    external = set()
    imports_by_file = {}
    pending = ["tesseract.exe"]
    while pending:
        name = pending.pop()
        imports = pe_imports(files[name])
        imports_by_file[name] = sorted(imports)
        for imported in imports:
            if imported in files:
                if imported not in needed:
                    needed.add(imported)
                    pending.append(imported)
            else:
                external.add(imported)
    non_root_dlls = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.dll")
                           if path.parent != root)
    return {
        "schema_version": "plm.tesseract-static-pe-dependencies.v1",
        "status": "STATIC_IMPORT_GRAPH_ONLY",
        "release_eligible": False,
        "needed_local_files": sorted(needed),
        "unused_local_dlls": sorted(name for name in files if name.endswith(".dll") and name not in needed),
        "non_root_dlls_not_in_static_graph": non_root_dlls,
        "external_import_names": sorted(external),
        "imports_by_file": imports_by_file,
        "needed_sha256": {name: hashlib.sha256(files[name].read_bytes()).hexdigest()
                          for name in sorted(needed)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "status", "release_eligible", "needed_local_files", "unused_local_dlls",
        "non_root_dlls_not_in_static_graph", "external_import_names")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
