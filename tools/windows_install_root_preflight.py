"""Fail closed on Windows install roots unsafe for the pinned OCR native runtime.

The current Tesseract candidate fails at language discovery under non-ASCII
installation paths. This preflight does not install or upgrade anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import PureWindowsPath


RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


def validate_install_root(value: str) -> str:
    if not value or not value.isascii() or any(ord(char) < 32 for char in value):
        raise ValueError("install root must be nonempty ASCII text")
    if value.startswith(("\\\\", "//")) or "/" in value:
        raise ValueError("UNC and slash-style install roots are unsupported")
    if not re.fullmatch(r"[A-Za-z]:\\.+", value):
        raise ValueError("install root must be an absolute drive path below its root")
    components = value[3:].split("\\")
    if any(not part or part in {".", ".."} or part.endswith((" ", "."))
           or any(char in '<>:"|?*' for char in part)
           or part.split(".", 1)[0].upper() in RESERVED for part in components):
        raise ValueError("install root contains an unsafe Windows component")
    path = PureWindowsPath(value)
    if not path.is_absolute() or len(path.parts) < 2:
        raise ValueError("install root must be below a drive root")
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args()
    try:
        root = validate_install_root(args.install_root)
    except ValueError as error:
        print(json.dumps({"status": "REJECTED", "reason": str(error), "release_eligible": False}), file=sys.stderr)
        return 2
    print(json.dumps({"status": "WINDOWS_INSTALL_ROOT_PREFLIGHT_PASS", "install_root": root,
                      "release_eligible": False}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
