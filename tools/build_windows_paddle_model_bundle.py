"""Build and verify a pinned, NON-RELEASE offline Paddle model sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

import audit_paddle_model_revisions as source_audit


EXPECTED_FINGERPRINT = "511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4"
FILES = ("config.json", "inference.json", "inference.pdiparams", "inference.yml", "README.md")
RUNTIME_FILES = FILES[:4]
MAX_EXPANDED = 128 * 1024 * 1024


def _entry(role: str, name: str) -> str:
    return f"models/PP-OCRv5_mobile_{role}/{name}"


def _object_id(data: bytes, lfs: bool) -> str:
    return (hashlib.sha256(data).hexdigest() if lfs else
            hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest())


def _fingerprint(contents: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for role in ("det", "rec"):
        digest.update(role.encode("ascii"))
        for name in RUNTIME_FILES:
            digest.update(name.encode("ascii"))
            digest.update(contents[_entry(role, name)])
    return digest.hexdigest()


def _zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build(det: Path, rec: Path, output: Path) -> dict:
    source = source_audit.audit(det, rec)
    contents = {}
    for role, directory in (("det", det), ("rec", rec)):
        for name in FILES:
            contents[_entry(role, name)] = (directory / name).read_bytes()
    fingerprint = _fingerprint(contents)
    if fingerprint != EXPECTED_FINGERPRINT:
        raise ValueError("pinned model fingerprint mismatch")
    manifest = {
        "kind": "WINDOWS_PADDLE_MODELS_NON_RELEASE",
        "schema_version": "plm.windows-paddle-model-sidecar.v1",
        "release_eligible": False,
        "model_fingerprint": fingerprint,
        "models": {role: {"revision": source["models"][role]["revision"]}
                   for role in ("det", "rec")},
        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
                  for name, data in sorted(contents.items())},
    }
    if output.exists():
        raise ValueError("model bundle output already exists")
    with zipfile.ZipFile(output, "x") as archive:
        archive.writestr(_zipinfo("manifest.json"), json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n")
        for name, data in sorted(contents.items()):
            archive.writestr(_zipinfo(name), data)
    return verify(output)


def verify(bundle: Path) -> dict:
    with zipfile.ZipFile(bundle) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise ValueError("model bundle inventory rejected")
        expected_names = {"manifest.json"} | {_entry(role, name) for role in ("det", "rec") for name in FILES}
        if set(names) != expected_names or any(
            not name.isascii() or "\\" in name or name.startswith("/") or ":" in name or
            any(part in ("", ".", "..") for part in name.split("/")) or
            stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK
            for info, name in zip(infos, names)
        ):
            raise ValueError("model bundle path rejected")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS_PADDLE_MODELS_NON_RELEASE" or
            manifest.get("release_eligible") is not False or
            manifest.get("model_fingerprint") != EXPECTED_FINGERPRINT or
            set(manifest.get("files", {})) != expected_names - {"manifest.json"}):
            raise ValueError("model bundle manifest rejected")
        contents = {}
        for role in ("det", "rec"):
            spec = source_audit.MODELS[role]
            if manifest.get("models", {}).get(role, {}).get("revision") != spec["revision"]:
                raise ValueError("model bundle revision mismatch")
            for filename in FILES:
                name = _entry(role, filename)
                data = archive.read(name)
                expected = manifest["files"][name]
                if (expected != {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)} or
                    _object_id(data, filename == "inference.pdiparams") != spec["objects"][filename]):
                    raise ValueError(f"model bundle upstream object mismatch: {name}")
                contents[name] = data
            readme = contents[_entry(role, "README.md")].decode("utf-8")
            if "license: apache-2.0" not in readme.lower().splitlines()[:10]:
                raise ValueError("model license declaration missing")
        if _fingerprint(contents) != EXPECTED_FINGERPRINT:
            raise ValueError("model bundle runtime fingerprint mismatch")
    return {"status": "PINNED_OFFLINE_MODEL_BUNDLE_PASS", "release_eligible": False,
            "archive_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "file_count": len(contents), "model_fingerprint": EXPECTED_FINGERPRINT}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--det", required=True, type=Path)
    parser.add_argument("--rec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.det, args.rec, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
