"""Verify cached Paddle OCR model bytes against pinned upstream Git/LFS objects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MODELS = {
    "det": {
        "revision": "0d63e78e2b680928f6b1747d76a08db6e645efb7",
        "objects": {
            "config.json": "4fc190d78e4425094b31a2d3a4744a3623d00b50",
            "inference.json": "6cd678f39460a27372f8fe570e4e12e7a383418f",
            "inference.pdiparams": "afa1820cb16c1fd0dad589d0f8b389139061c1ef6d68019685fd07be997dda5b",
            "inference.yml": "579d10695d2dd6e85c5ecba02d151ae5c077aa49",
            "README.md": "6ed97ac58de2375d7010fa6b7562b762d5e804f9",
        },
    },
    "rec": {
        "revision": "682f20538d8c086cb2128e5cfac775e6c4904e85",
        "objects": {
            "config.json": "17e7b3034d8cd2247ff56d19d6b437c2d5fb8864",
            "inference.json": "90f76a83768033cbd2bc9aa4d10aaa08e7bf25f7",
            "inference.pdiparams": "2460da90875937c94db97eba74ae3d9e5d4c4c57c42f1f41531c09a26bcc771a",
            "inference.yml": "176f6d552a120e6fa0a812089fb36c1bb983ce28",
            "README.md": "07d22daf5a4654c6a60f7447337cd3ccd38ac179",
        },
    },
}


def _object_id(path: Path, lfs: bool) -> str:
    data = path.read_bytes()
    if lfs:
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def audit(det: Path, rec: Path) -> dict:
    result = {}
    for role, directory in (("det", det), ("rec", rec)):
        spec = MODELS[role]
        files = {}
        for name, expected in spec["objects"].items():
            path = directory / name
            actual = _object_id(path, name == "inference.pdiparams")
            if actual != expected:
                raise ValueError(f"{role}/{name} upstream object mismatch")
            if name != "README.md":
                metadata = directory / ".cache" / "huggingface" / "download" / f"{name}.metadata"
                lines = metadata.read_text(encoding="utf-8").splitlines()
                if len(lines) < 2 or lines[:2] != [spec["revision"], expected]:
                    raise ValueError(f"{role}/{name} cache revision mismatch")
            files[name] = {"object_id": actual, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        readme = (directory / "README.md").read_text(encoding="utf-8")
        if "license: apache-2.0" not in readme.lower().splitlines()[:10]:
            raise ValueError(f"{role} upstream license declaration missing")
        result[role] = {"revision": spec["revision"], "files": files}
    return {"status": "PINNED_MODEL_BYTES_PASS", "release_eligible": False, "models": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--det", required=True, type=Path)
    parser.add_argument("--rec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.det, args.rec)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
