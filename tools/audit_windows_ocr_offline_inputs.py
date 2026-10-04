"""Check exact local OCR inputs without claiming a complete offline installer."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from audit_windows_candidate_licenses import digest_file
from verify_windows11_embedded_candidate import inspect_archive


GHOSTSCRIPT_SHA256 = "52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50"
OCRMYPDF_SHA256 = "d1fc83dd2b567011f10afdd7612576f13c40183cbf1d867f898b64bb62d5f515"
MODEL_FINGERPRINT = "511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4"
TESSDATA_HASHES = {
    "chi_sim_vert.traineddata": "ea672a78157199c333aa12ec4e74550077689b545df5fc770903716850c8b2e5",
    "chi_sim.traineddata": "4fef2d1306c8e87616d4d3e4c6c67faf5d44be3342290cf8f2f0f6e3aa7e735b",
    "eng.traineddata": "8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba",
    "osd.traineddata": "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff",
}
MODEL_FILES = ("config.json", "inference.json", "inference.pdiparams", "inference.yml")


def model_fingerprint(det: Path, rec: Path) -> str:
    digest = hashlib.sha256()
    for role, directory in (("det", det), ("rec", rec)):
        digest.update(role.encode("ascii"))
        for name in MODEL_FILES:
            digest.update(name.encode("ascii"))
            with (directory / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def audit_ocr(candidate: Path, gs_installer: Path, ocrmypdf_wheel: Path,
              tessdata: Path, det: Path, rec: Path, tesseract: Path) -> dict:
    manifest, _, _ = inspect_archive(candidate)
    if manifest.get("release_eligible") is not False:
        raise ValueError("candidate release gate rejected")
    if gs_installer.name != "gs10080w64.exe" or digest_file(gs_installer) != GHOSTSCRIPT_SHA256:
        raise ValueError("Ghostscript installer source mismatch")
    if ocrmypdf_wheel.name != "ocrmypdf-17.12.1-py3-none-any.whl" or digest_file(ocrmypdf_wheel) != OCRMYPDF_SHA256:
        raise ValueError("OCRmyPDF wheel source mismatch")
    if {p.name for p in tessdata.iterdir() if p.is_file() and p.suffix == ".traineddata"} != set(TESSDATA_HASHES):
        raise ValueError("tessdata inventory mismatch")
    for name, expected in TESSDATA_HASHES.items():
        if digest_file(tessdata / name) != expected:
            raise ValueError("tessdata hash mismatch")
    fingerprint = model_fingerprint(det, rec)
    if fingerprint != MODEL_FINGERPRINT:
        raise ValueError("Paddle model fingerprint mismatch")
    model_license_declarations = {}
    for role, directory in (("det", det), ("rec", rec)):
        readme = (directory / "README.md").read_text(encoding="utf-8")
        model_license_declarations[role] = "license: apache-2.0" in readme.lower().splitlines()[:10]
    if not all(model_license_declarations.values()):
        raise ValueError("Paddle model license declaration missing")
    if not tesseract.is_file() or tesseract.name.casefold() != "tesseract.exe":
        raise ValueError("installed Tesseract missing")
    probe = subprocess.run([str(tesseract), "--version"], capture_output=True, text=True, timeout=20, check=False)
    first_line = (probe.stdout or probe.stderr).splitlines()[:1]
    if probe.returncode or not first_line or not first_line[0].startswith("tesseract v5.4.0.20240606"):
        raise ValueError("installed Tesseract version mismatch")
    with zipfile.ZipFile(candidate) as archive:
        names = [name.casefold() for name in archive.namelist()]
    candidate_presence = {
        "ghostscript_executable": any(name.endswith(("/gswin64c.exe", "/gswin64.exe")) for name in names),
        "tesseract_executable": any(name.endswith("/tesseract.exe") for name in names),
        "ocrmypdf_package": any(name.startswith("payload/runtime/packages/ocrmypdf/") for name in names),
        "tessdata": any(name.endswith("/chi_sim.traineddata") for name in names),
        "paddle_model": any(name.endswith("/pp-ocrv5_mobile_det/inference.pdiparams") for name in names),
    }
    return {
        "schema_version": "plm.windows-ocr-offline-inputs.v1",
        "status": "INPUT_BYTES_VERIFIED_DEPLOYMENT_INCOMPLETE",
        "release_eligible": False,
        "candidate_sha256": digest_file(candidate),
        "ghostscript_installer_sha256": GHOSTSCRIPT_SHA256,
        "ocrmypdf_wheel_sha256": OCRMYPDF_SHA256,
        "tessdata_sha256": TESSDATA_HASHES,
        "paddle_model_fingerprint": fingerprint,
        "paddle_model_license_declaration": model_license_declarations,
        "tesseract_installed_version": first_line[0],
        "tesseract_installed_exe_sha256": digest_file(tesseract),
        "tesseract_installer_staged": False,
        "candidate_presence": candidate_presence,
        "limits": ["Tesseract installer provenance not established", "Paddle upstream artifact revision not fixed", "No Ghostscript/PyMuPDF legal approval", "No clean target-machine installation"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local OCR inputs for a non-release Windows candidate")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--gs-installer", required=True, type=Path)
    parser.add_argument("--ocrmypdf-wheel", required=True, type=Path)
    parser.add_argument("--tessdata", required=True, type=Path)
    parser.add_argument("--det", required=True, type=Path)
    parser.add_argument("--rec", required=True, type=Path)
    parser.add_argument("--tesseract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_ocr(args.candidate, args.gs_installer, args.ocrmypdf_wheel,
                       args.tessdata, args.det, args.rec, args.tesseract)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "release_eligible", "tesseract_installer_staged", "candidate_presence")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
