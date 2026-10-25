"""Map a verified NON-RELEASE ZIP into an isolated Windows install rehearsal.

Never touches C:\\PLMTool, SCM, an existing database, or customer data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from build_windows_paddle_model_bundle import EXPECTED_FINGERPRINT, RUNTIME_FILES
from build_windows_unified_pg18_candidate import KIND
from package_windows_embedded_candidate import digest_path
from package_windows_unified_candidate import safe_name
from plan_windows_unified_pg18_composition import inspect
from plan_windows_unified_pg18_install import CANDIDATE_SHA256
from verify_windows_unified_extract import verify, windows_long_path


ROOT_NAME = re.compile(r"plm-install-rehearsal-[A-Za-z0-9_-]{8,64}\Z")
META = ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json")


def target_name(source: str) -> str:
    safe_name(source)
    prefixes = (
        ("payload/runtime/", "runtime/python/"),
        ("payload/pgsql/", "runtime/pgsql/"),
        ("payload/frontend/", "app/frontend/"),
        ("payload/ocr/models/", "app/models/"),
        ("payload/ocr/", "app/ocr/"),
        ("payload/config/", "config/"),
        ("payload/third-party-licenses/", "app/third-party-licenses/"),
    )
    for prefix, mapped in prefixes:
        if source.startswith(prefix) and len(source) > len(prefix):
            return safe_name(mapped + source[len(prefix):])
    if source in META:
        return "app/package-metadata/" + source
    raise ValueError("unmapped candidate payload family")


def validate_output_root(root: Path) -> Path:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    try:
        parent = root.parent.resolve(strict=True)
    except OSError:
        raise ValueError("rehearsal root must be a fresh direct ASCII Temp child") from None
    if (parent != temp or not str(root).isascii()
            or not ROOT_NAME.fullmatch(root.name) or root.exists() or root.is_symlink()):
        raise ValueError("rehearsal root must be a fresh direct ASCII Temp child")
    return root


def _copy_checked(source: Path, destination: Path, expected: str) -> None:
    os.makedirs(windows_long_path(destination.parent), exist_ok=True)
    digest = hashlib.sha256()
    with open(windows_long_path(source), "rb") as inp, open(windows_long_path(destination), "xb") as out:
        while block := inp.read(1024 * 1024):
            out.write(block)
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("layout copy source hash mismatch")


def _model_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for role in ("det", "rec"):
        digest.update(role.encode("ascii"))
        for name in RUNTIME_FILES:
            digest.update(name.encode("ascii"))
            with (root / f"PP-OCRv5_mobile_{role}" / name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def _run(arguments: list[str], env: dict[str, str], *, timeout: int = 120) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, errors="replace",
                            env=env, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError(f"isolated layout probe failed: {Path(arguments[0]).name}, exit={result.returncode}")
    return (result.stdout or result.stderr).strip()


def rehearse(candidate: Path, stage: Path, output_root: Path) -> dict:
    validate_output_root(output_root)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (stage.resolve(strict=True).parent != temp or not str(stage).isascii()
            or stage == output_root):
        raise ValueError("source stage must be a direct ASCII Temp child")
    manifest, inspected = inspect(candidate, CANDIDATE_SHA256, KIND, 21103)
    hashes = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        digest, name = line.split("  ", 1)
        if name in hashes:
            raise ValueError("duplicate source payload path")
        hashes[name] = digest
    if ({name.casefold(): digest for name, digest in hashes.items()} != inspected
            or verify(stage, expected_kind=KIND)["payload_file_count"] != len(hashes)):
        raise ValueError("source stage count mismatch")
    with zipfile.ZipFile(candidate) as archive:
        for name in META:
            if (stage / name).read_bytes() != archive.read(name):
                raise ValueError("source stage metadata differs from candidate")
    mapping = {name: target_name(name) for name in (*hashes, *META)}
    if len(mapping) != len(hashes) + len(META) or len({name.casefold() for name in mapping.values()}) != len(mapping):
        raise ValueError("rehearsal mapping collision")
    output_root.mkdir(mode=0o700)
    for name in sorted(mapping):
        expected = hashes[name] if name in hashes else digest_path(stage / name)
        _copy_checked(stage / name, output_root / mapping[name], expected)
    for name in ("plugins", "data", "logs", "license"):
        (output_root / name).mkdir()
    for source, target in mapping.items():
        if digest_path(output_root / target) != (hashes[source] if source in hashes else digest_path(stage / source)):
            raise ValueError("rehearsal target readback hash mismatch")
    model_root = output_root / "app/models"
    fingerprint = _model_fingerprint(model_root)
    if fingerprint != EXPECTED_FINGERPRINT:
        raise ValueError("rehearsal OCR model fingerprint mismatch")
    config = output_root / "config/bootstrap.rehearsal.yaml"
    config.write_bytes((
        'bind_host: "127.0.0.1"\n'
        'bind_port: 8000\n'
        f'data_root: "{(output_root / "data").as_posix()}"\n'
        'log_level: "INFO"\n'
        f'parser_ocr_detection_model_dir: "{(model_root / "PP-OCRv5_mobile_det").as_posix()}"\n'
        f'parser_ocr_recognition_model_dir: "{(model_root / "PP-OCRv5_mobile_rec").as_posix()}"\n'
        f'parser_ocr_model_fingerprint: "{fingerprint}"\n'
    ).encode("utf-8"))
    runtime = output_root / "runtime/python"
    native = output_root / "app/ocr"
    pg = output_root / "runtime/pgsql"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(native / "tesseract"),
                                   str(native / "ghostscript/bin"), str(pg / "bin"),
                                   str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    imported = _run([str(runtime / "python.exe"), "-I", "-B", "-c",
                     'import plm_assistant,fastapi,sqlalchemy,psycopg,paddle,paddleocr,paddlex,ocrmypdf; import plm_assistant.entrypoints.service_windows; print(plm_assistant.__version__)'], env)
    service_raw = _run([str(runtime / "python.exe"), "-I", "-B", "-m",
                        "plm_assistant.entrypoints.service_plan_windows", str(runtime / "python.exe"), str(config)], env)
    service_plan = json.loads(service_raw)
    if imported != "0.1.0.dev0" or service_plan.get("status") != "PLAN_ONLY" or len(service_plan.get("service_commands", [])) != 3:
        raise ValueError("isolated service command plan rejected")
    tess = _run([str(native / "tesseract/tesseract.exe"), "--version"], env).splitlines()[0]
    ghost = _run([str(native / "ghostscript/bin/gswin64c.exe"), "--version"], env)
    pg_version = _run([str(pg / "bin/pg_config.exe"), "--version"], env)
    if not tess.startswith("tesseract 5.5.3") or ghost != "10.08.0" or pg_version != "PostgreSQL 18.6":
        raise ValueError("isolated native component version mismatch")
    if digest_path(candidate) != CANDIDATE_SHA256 or verify(stage, expected_kind=KIND)["payload_file_count"] != len(hashes):
        raise ValueError("source candidate or stage changed during layout rehearsal")
    return {"status": "NON_RELEASE_ISOLATED_LAYOUT_PASS", "release_eligible": False,
            "candidate_sha256": CANDIDATE_SHA256, "rehearsal_root": str(output_root),
            "copied_payload_count": len(hashes), "service_plan_role_count": 3,
            "python_version": imported, "postgresql_version": pg_version,
            "tesseract_version": tess, "ghostscript_version": ghost,
            "model_fingerprint": fingerprint, "scm_changed": False,
            "database_started": False, "formal_install_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.candidate, args.stage, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
