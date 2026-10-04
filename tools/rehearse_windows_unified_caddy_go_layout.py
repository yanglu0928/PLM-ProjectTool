"""Copy fixed P33 staging into a NEW ASCII Temp install layout; verify every byte."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_caddy_windows_offline_input import EXE_SHA256, digest
from audit_go_stdlib_source_input import GO_LICENSE_SHA256, GO_SOURCE_SHA256
from build_windows_paddle_model_bundle import EXPECTED_FINGERPRINT
from build_windows_unified_caddy_candidate import TEMPLATE_SHA256
from build_windows_unified_caddy_go_source_candidate import (
    GO_LICENSE_MEMBER, GO_SOURCE_MEMBER, KIND,
)
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from rehearse_windows_unified_pg18_layout import (
    _copy_checked, _model_fingerprint, _run, validate_output_root,
)
from smoke_caddy_same_origin_https import synthetic_certificate
from smoke_staged_caddy_template import render
from verify_windows_unified_caddy_go_source_candidate import (
    ARCHIVE_SHA256, verify as verify_candidate,
)
from verify_windows_unified_extract import verify as verify_stage


def rehearse(candidate: Path, source: Path, stage: Path, output_root: Path) -> dict:
    validate_output_root(output_root)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if (stage.resolve(strict=True).parent != temp or not str(stage).isascii()
            or stage == output_root or Path("C:\\PLMTool").exists()):
        raise ValueError("source stage must be separate ASCII Temp; formal root must be absent")
    identity = verify_candidate(candidate, source)
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("source stage count differs")
    hashes: dict[str, str] = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        value, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("source stage manifest rejected")
        hashes[name] = value
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("source stage metadata differs from fixed ZIP")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if (len(hashes) != 21112 or len(mapping) != 21115
            or mapping.get(GO_SOURCE_MEMBER) != "app/third-party-sources/go/go1.26.3.src.tar.gz"
            or mapping.get(GO_LICENSE_MEMBER) != "app/third-party-licenses/go/LICENSE"):
        raise ValueError("new source target mapping differs")
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    for original, target in sorted(mapping.items()):
        _copy_checked(stage / original, output_root / target,
                      hashes[original] if original in hashes else digest_path(stage / original))
    landed = {str(path.relative_to(output_root)).replace("\\", "/").casefold()
              for path in output_root.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("new layout target file set differs")
    for original, target in mapping.items():
        if digest_path(output_root / target) != (hashes[original] if original in hashes else digest_path(stage / original)):
            raise ValueError("new layout target hash differs")
    if _model_fingerprint(output_root / "app/models") != EXPECTED_FINGERPRINT:
        raise ValueError("new layout OCR model fingerprint differs")
    go_source = output_root / mapping[GO_SOURCE_MEMBER]
    go_license = output_root / mapping[GO_LICENSE_MEMBER]
    caddy = output_root / "runtime/caddy/caddy.exe"
    template = output_root / "config/Caddyfile.template"
    if (digest(go_source) != GO_SOURCE_SHA256 or digest(go_license) != GO_LICENSE_SHA256
            or digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256):
        raise ValueError("new layout Go/Caddy evidence identity differs")
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
    if imported != "0.1.0.dev0" or pg_version != "PostgreSQL 18.6" or not caddy_version.startswith("v2.11.4 "):
        raise ValueError("new layout runtime version differs")
    with tempfile.TemporaryDirectory(prefix="plm-caddy-go-layout-cert-") as directory:
        root = Path(directory)
        cert, key, config = root / "cert.pem", root / "key.pem", root / "Caddyfile"
        synthetic_certificate(cert, key)
        config.write_text(render(template.read_text(encoding="ascii"), cert=cert, key=key,
                                 frontend=output_root / "app/frontend/dist",
                                 api_port=18080, https_port=18443), encoding="ascii")
        result = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                capture_output=True, text=True, errors="replace", env=env, timeout=20)
        if result.returncode:
            raise ValueError("new layout Caddyfile validation failed")
    if verify_candidate(candidate, source) != identity or verify_stage(stage, expected_kind=KIND) != checked:
        raise ValueError("new candidate or stage changed during layout rehearsal")
    return {"status": "NON_RELEASE_CADDY_GO_SOURCE_ISOLATED_LAYOUT_PASS",
            "release_eligible": False, "candidate_sha256": ARCHIVE_SHA256,
            "mapping_sha256": mapping_sha256, "layout_root": str(output_root),
            "copied_file_count": len(mapping), "python_version": imported,
            "postgresql_version": pg_version, "caddy_version": caddy_version,
            "go_source_sha256": GO_SOURCE_SHA256,
            "synthetic_template_validate": True,
            "formal_install_performed": False, "services_changed": False,
            "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.candidate, args.source, args.stage, args.output_root),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
