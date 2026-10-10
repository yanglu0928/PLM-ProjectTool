"""Verify the fixed native OCR notice candidate in a fresh isolated Windows layout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import EXE_SHA256, digest
from audit_ghostscript_portable_payload import EXE_SHA256 as GS_EXE_SHA256
from audit_ghostscript_source_input import SOURCE_SHA256
from audit_go_stdlib_source_input import GO_LICENSE_SHA256, GO_SOURCE_SHA256
from build_windows_paddle_model_bundle import EXPECTED_FINGERPRINT
from build_windows_unified_caddy_candidate import TEMPLATE_SHA256
from build_windows_unified_caddy_go_source_candidate import GO_LICENSE_MEMBER, GO_SOURCE_MEMBER
from build_windows_unified_ghostscript_source_candidate import (
    LICENSE_MEMBER, LICENSE_SHA256, SOURCE_MEMBER,
)
from build_windows_unified_native_ocr_notice_candidate import KIND, INDEX, PREFIX, README
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from rehearse_windows_unified_pg18_layout import (
    _copy_checked, _model_fingerprint, _run, validate_output_root,
)
from smoke_caddy_same_origin_https import synthetic_certificate
from smoke_staged_caddy_template import render
from verify_windows_unified_extract import verify as verify_stage
from verify_windows_unified_native_ocr_notice_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)


def license_targets(mapping: dict[str, str], review: dict) -> dict[str, str]:
    if (len(review.get("evidence", [])) != 61 or review.get("unique_text_count") != 42
            or review.get("legal_clearance") is not False
            or review.get("release_eligible") is not False):
        raise ValueError("native OCR review population or gate differs")
    texts = {}
    for item in review["evidence"]:
        source = item.get("text_path")
        sha = item.get("text_sha256")
        if (not isinstance(source, str) or not source.startswith(PREFIX + "texts/")
                or not isinstance(sha, str) or source != PREFIX + "texts/" + sha + ".txt"
                or mapping.get(source) != "app/third-party-licenses/native-ocr/texts/" + sha + ".txt"
                or item.get("release_obligations_reviewed") != "NO"):
            raise ValueError("native OCR text target mapping differs")
        texts[source] = sha
    if (len(texts) != 42
            or mapping.get(INDEX) != "app/third-party-licenses/native-ocr/review-map.json"
            or mapping.get(README) != "app/third-party-licenses/native-ocr/README.txt"):
        raise ValueError("native OCR review sidecar mapping differs")
    return texts


def rehearse(candidate: Path, parent: Path, ancestor: Path, grandparent: Path,
             native_matrix: Path, stage: Path, output_root: Path) -> dict:
    validate_output_root(output_root)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (stage.resolve(strict=True).parent != temp or not str(stage).isascii()
            or stage == output_root or Path("C:\\PLMTool").exists()):
        raise ValueError("notice stage must be separate ASCII Temp; formal root must be absent")
    identity = verify_candidate(candidate, parent, ancestor, grandparent, native_matrix)
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("native OCR notice stage count differs")
    hashes: dict[str, str] = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        value, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("native OCR notice stage hash list rejected")
        hashes[name] = value
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("native OCR notice stage metadata differs from fixed ZIP")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    required = {
        SOURCE_MEMBER: "app/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz",
        LICENSE_MEMBER: "app/third-party-licenses/ghostscript/source-LICENSE",
        GO_SOURCE_MEMBER: "app/third-party-sources/go/go1.26.3.src.tar.gz",
        GO_LICENSE_MEMBER: "app/third-party-licenses/go/LICENSE",
    }
    if (len(hashes) != 21158 or len(mapping) != 21161
            or any(mapping.get(source) != target for source, target in required.items())):
        raise ValueError("native OCR notice target mapping differs")
    review = json.loads((stage / INDEX).read_text(encoding="utf-8"))
    texts = license_targets(mapping, review)
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    for original, target in sorted(mapping.items()):
        _copy_checked(stage / original, output_root / target,
                      hashes[original] if original in hashes else digest_path(stage / original))
    landed = {str(path.relative_to(output_root)).replace("\\", "/").casefold()
              for path in output_root.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("native OCR notice layout file set differs")
    for original, target in mapping.items():
        if digest_path(output_root / target) != (hashes[original] if original in hashes
                                                       else digest_path(stage / original)):
            raise ValueError("native OCR notice layout target hash differs")
    for source, sha in texts.items():
        if digest(output_root / mapping[source]) != sha:
            raise ValueError("native OCR notice layout text differs")
    if _model_fingerprint(output_root / "app/models") != EXPECTED_FINGERPRINT:
        raise ValueError("native OCR notice layout model fingerprint differs")
    caddy = output_root / "runtime/caddy/caddy.exe"
    template = output_root / "config/Caddyfile.template"
    ghost = output_root / "app/ocr/ghostscript/bin/gswin64c.exe"
    if (digest(output_root / mapping[SOURCE_MEMBER]) != SOURCE_SHA256
            or digest(output_root / mapping[LICENSE_MEMBER]) != LICENSE_SHA256
            or digest(output_root / mapping[GO_SOURCE_MEMBER]) != GO_SOURCE_SHA256
            or digest(output_root / mapping[GO_LICENSE_MEMBER]) != GO_LICENSE_SHA256
            or digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256
            or digest(ghost) != GS_EXE_SHA256):
        raise ValueError("native OCR notice layout runtime or source identity differs")
    runtime = output_root / "runtime/python"
    pg = output_root / "runtime/pgsql"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(pg / "bin"),
                                   str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    imported = _run([str(runtime / "python.exe"), "-I", "-B", "-c",
                     "import plm_assistant,fastapi,sqlalchemy,psycopg,paddle,paddleocr,paddlex,ocrmypdf; "
                     "print(plm_assistant.__version__)"], env)
    pg_version = _run([str(pg / "bin/pg_config.exe"), "--version"], env)
    caddy_version = _run([str(caddy), "version"], env)
    ghost_version = _run([str(ghost), "--version"], env)
    if (imported != "0.1.0.dev0" or pg_version != "PostgreSQL 18.6"
            or not caddy_version.startswith("v2.11.4 ") or ghost_version != "10.08.0"):
        raise ValueError("native OCR notice layout runtime version differs")
    with tempfile.TemporaryDirectory(prefix="plm-native-ocr-layout-cert-") as directory:
        temp_cert = Path(directory)
        cert, key, config = temp_cert / "cert.pem", temp_cert / "key.pem", temp_cert / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(render(template.read_text(encoding="ascii"), cert=cert, key=key,
                                 frontend=output_root / "app/frontend/dist",
                                 api_port=18080, https_port=18443), encoding="ascii")
        result = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                capture_output=True, text=True, errors="replace", env=env, timeout=20)
        if result.returncode:
            raise ValueError("native OCR notice layout synthetic Caddyfile validation failed")
    if (verify_candidate(candidate, parent, ancestor, grandparent, native_matrix) != identity
            or verify_stage(stage, expected_kind=KIND) != checked):
        raise ValueError("native OCR notice candidate or stage changed during rehearsal")
    return {"status": "NON_RELEASE_NATIVE_OCR_NOTICE_ISOLATED_LAYOUT_PASS",
            "release_eligible": False, "legal_clearance": False,
            "candidate_sha256": ARCHIVE_SHA256, "mapping_sha256": mapping_sha256,
            "layout_root": str(output_root), "copied_file_count": len(mapping),
            "license_text_count": len(texts), "evidence_record_count": len(review["evidence"]),
            "python_version": imported, "postgresql_version": pg_version,
            "caddy_version": caddy_version, "ghostscript_version": ghost_version,
            "synthetic_template_validate": True,
            "formal_install_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "parent", "ancestor", "grandparent", "native-matrix", "stage", "output-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.candidate, args.parent, args.ancestor, args.grandparent,
                              args.native_matrix, args.stage, args.output_root),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
