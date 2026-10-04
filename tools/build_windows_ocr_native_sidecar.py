"""Build a local NON-RELEASE Windows OCR native/model sidecar from pinned inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

import audit_ghostscript_portable_payload as gs_audit
import audit_tesseract_official_payload as tess_audit
import audit_windows_ocr_offline_inputs as ocr_inputs
import build_windows_paddle_model_bundle as paddle_bundle


MAX_EXPANDED = 512 * 1024 * 1024
EXPECTED_FILES = 654 + 139 + 4 + 10


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(prefix: str, path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    name = f"payload/ocr/{prefix}/{relative}"
    if (not name.isascii() or "\\" in name or ":" in name or
        any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("native payload path rejected")
    return name


def _zipinfo(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build(*, tess_installer: Path, tess_payload: Path, gs_installer: Path,
          gs_payload: Path, sevenzip: Path, tessdata: Path,
          paddle_archive: Path, output: Path) -> dict:
    tess_report = tess_audit.audit(tess_installer, tess_payload, sevenzip)
    gs_report = gs_audit.audit(gs_installer, gs_payload, sevenzip)
    paddle_report = paddle_bundle.verify(paddle_archive)
    contents: dict[str, bytes] = {}
    for prefix, root, report in (
        ("tesseract", tess_payload, tess_report),
        ("ghostscript", gs_payload, gs_report),
    ):
        for item in report["files"]:
            path = root / item["path"]
            data = path.read_bytes()
            if _digest(data) != item["sha256"]:
                raise ValueError("native source changed after independent audit")
            contents[_entry(prefix, path, root)] = data
    trained = {path.name for path in tessdata.glob("*.traineddata")}
    if trained != set(ocr_inputs.TESSDATA_HASHES):
        raise ValueError("tessdata inventory mismatch")
    for name, expected in ocr_inputs.TESSDATA_HASHES.items():
        data = (tessdata / name).read_bytes()
        if _digest(data) != expected:
            raise ValueError("tessdata source hash mismatch")
        contents[f"payload/ocr/tesseract/tessdata/{name}"] = data
    with zipfile.ZipFile(paddle_archive) as archive:
        for role in ("det", "rec"):
            for filename in paddle_bundle.FILES:
                name = paddle_bundle._entry(role, filename)
                contents[f"payload/ocr/{name}"] = archive.read(name)
    if len(contents) != EXPECTED_FILES or sum(map(len, contents.values())) > MAX_EXPANDED:
        raise ValueError("native sidecar inventory rejected")
    manifest = {
        "kind": "WINDOWS11_OCR_NATIVE_NON_RELEASE",
        "schema_version": "plm.windows-ocr-native-sidecar.v1",
        "release_eligible": False,
        "license_status": "REVIEW_REQUIRED",
        "tesseract_installer_sha256": tess_report["installer_sha256"],
        "ghostscript_installer_sha256": gs_report["installer_sha256"],
        "paddle_archive_sha256": paddle_report["archive_sha256"],
        "paddle_model_fingerprint": paddle_report["model_fingerprint"],
        "files": {name: {"sha256": _digest(data), "size": len(data)}
                  for name, data in sorted(contents.items())},
        "known_blockers": ["Tesseract Authenticode and transitive DLL/JAR license attribution",
                           "Ghostscript AGPL public corresponding source/product license review",
                           "controlled ACL/service account and target OS release acceptance"],
    }
    if output.exists():
        raise ValueError("native sidecar output already exists")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=1, allowZip64=True) as archive:
        archive.writestr(_zipinfo("manifest.json"),
                         json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n")
        for name, data in sorted(contents.items()):
            archive.writestr(_zipinfo(name), data)
    return verify(output)


def verify(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(name.casefold() for name in names)):
            raise ValueError("native sidecar duplicate entry")
        if len(names) != EXPECTED_FILES + 1 or sum(info.file_size for info in infos) > MAX_EXPANDED:
            raise ValueError("native sidecar count or size rejected")
        for info in infos:
            name = info.filename
            if (not name.isascii() or "\\" in name or ":" in name or
                any(part in ("", ".", "..") for part in name.split("/")) or
                stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK):
                raise ValueError("native sidecar path rejected")
        manifest = json.loads(archive.read("manifest.json"))
        if (manifest.get("kind") != "WINDOWS11_OCR_NATIVE_NON_RELEASE" or
            manifest.get("release_eligible") is not False or
            manifest.get("license_status") != "REVIEW_REQUIRED" or
            manifest.get("tesseract_installer_sha256") != tess_audit.INSTALLER_SHA256 or
            manifest.get("ghostscript_installer_sha256") != gs_audit.INSTALLER_SHA256 or
            manifest.get("paddle_model_fingerprint") != paddle_bundle.EXPECTED_FINGERPRINT or
            set(manifest.get("files", {})) != set(names) - {"manifest.json"}):
            raise ValueError("native sidecar manifest rejected")
        tess_names = {name for name in names if name.startswith("payload/ocr/tesseract/")}
        gs_names = {name for name in names if name.startswith("payload/ocr/ghostscript/")}
        model_names = {f"payload/ocr/{paddle_bundle._entry(role, filename)}"
                       for role in ("det", "rec") for filename in paddle_bundle.FILES}
        if (len(tess_names) != 143 or len(gs_names) != 654 or
            not model_names.issubset(names) or
            set(names) != {"manifest.json"} | tess_names | gs_names | model_names):
            raise ValueError("native sidecar component inventory rejected")
        for name, expected in manifest["files"].items():
            data = archive.read(name)
            if expected != {"sha256": _digest(data), "size": len(data)}:
                raise ValueError(f"native sidecar file mismatch: {name}")
        model_contents = {}
        for role in ("det", "rec"):
            spec = paddle_bundle.source_audit.MODELS[role]
            for filename in paddle_bundle.FILES:
                model_name = paddle_bundle._entry(role, filename)
                data = archive.read(f"payload/ocr/{model_name}")
                if paddle_bundle._object_id(data, filename == "inference.pdiparams") != spec["objects"][filename]:
                    raise ValueError("native sidecar model upstream object mismatch")
                model_contents[model_name] = data
        if paddle_bundle._fingerprint(model_contents) != paddle_bundle.EXPECTED_FINGERPRINT:
            raise ValueError("native sidecar model runtime fingerprint mismatch")
        pinned = {
            "payload/ocr/tesseract/tesseract.exe": tess_audit.EXE_SHA256,
            "payload/ocr/tesseract/doc/LICENSE": tess_audit.LICENSE_SHA256,
            "payload/ocr/ghostscript/bin/gswin64c.exe": gs_audit.EXE_SHA256,
            "payload/ocr/ghostscript/doc/COPYING": gs_audit.COPYING_SHA256,
        }
        pinned.update({f"payload/ocr/tesseract/tessdata/{name}": value
                       for name, value in ocr_inputs.TESSDATA_HASHES.items()})
        for name, expected in pinned.items():
            if manifest["files"].get(name, {}).get("sha256") != expected:
                raise ValueError(f"native sidecar pinned byte mismatch: {name}")
    return {"status": "WINDOWS11_OCR_NATIVE_SIDECAR_BYTES_PASS",
            "release_eligible": False,
            "archive_sha256": gs_audit.digest(archive_path),
            "file_count": EXPECTED_FILES,
            "paddle_model_fingerprint": manifest["paddle_model_fingerprint"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("tess-installer", "tess-payload", "gs-installer", "gs-payload",
                 "sevenzip", "tessdata", "paddle-archive", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(**vars(args)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
