"""Copy fixed P22 staging into a fresh ASCII Temp install layout and read back every file.

This is a NON-RELEASE rehearsal, never the formal install or an SCM action.
"""

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
from build_windows_unified_caddy_candidate import KIND, TEMPLATE_SHA256
from build_windows_paddle_model_bundle import EXPECTED_FINGERPRINT
from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping, plan_install
from rehearse_windows_unified_pg18_layout import (
    _copy_checked, _model_fingerprint, _run, validate_output_root,
)
from smoke_caddy_same_origin_https import synthetic_certificate
from smoke_staged_caddy_template import render
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify as verify_source
from verify_windows_unified_extract import verify as verify_stage


def rehearse(candidate: Path, stage: Path, output_root: Path) -> dict:
    validate_output_root(output_root)
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    if stage.resolve(strict=True).parent != temp or not str(stage).isascii() or stage == output_root:
        raise ValueError("source stage must be a different direct ASCII Temp child")
    plan = plan_install(candidate, "C:\\PLMTool")
    if plan["install_root_exists"]:
        raise ValueError("formal install root already exists; rehearsal must not imply migration")
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != 21110:
        raise ValueError("source stage count changed")
    hashes: dict[str, str] = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        value, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("source manifest rejected")
        hashes[name] = value
    if len(hashes) != 21110:
        raise ValueError("source manifest count changed")
    with zipfile.ZipFile(candidate) as archive:
        for name in META:
            if (stage / name).read_bytes() != archive.read(name):
                raise ValueError("source metadata changed")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if mapping_sha256 != plan["mapping_sha256"]:
        raise ValueError("source stage and fixed candidate mapping differ")
    output_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    for source, target in sorted(mapping.items()):
        _copy_checked(stage / source, output_root / target,
                      hashes[source] if source in hashes else digest_path(stage / source))
    landed = {str(path.relative_to(output_root)).replace("\\", "/").casefold()
              for path in output_root.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("layout target file set differs")
    for source, target in mapping.items():
        if digest_path(output_root / target) != (hashes[source] if source in hashes else digest_path(stage / source)):
            raise ValueError("layout target readback differs")
    if _model_fingerprint(output_root / "app/models") != EXPECTED_FINGERPRINT:
        raise ValueError("layout OCR model fingerprint differs")
    caddy = output_root / "runtime/caddy/caddy.exe"
    template = output_root / "config/Caddyfile.template"
    if digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256:
        raise ValueError("layout Caddy/template identity differs")
    runtime = output_root / "runtime/python"
    native = output_root / "app/ocr"
    pg = output_root / "runtime/pgsql"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
    env.pop("PYTHONPATH", None)
    env["PATH"] = os.pathsep.join((str(runtime), str(native / "tesseract"),
                                   str(native / "ghostscript/bin"), str(pg / "bin"),
                                   str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
    imported = _run([str(runtime / "python.exe"), "-I", "-B", "-c",
                     "import plm_assistant,fastapi,sqlalchemy,psycopg,paddle,paddleocr,paddlex,ocrmypdf; "
                     "print(plm_assistant.__version__)"], env)
    pg_version = _run([str(pg / "bin/pg_config.exe"), "--version"], env)
    caddy_version = _run([str(caddy), "version"], env)
    if imported != "0.1.0.dev0" or pg_version != "PostgreSQL 18.6" or not caddy_version.startswith("v2.11.4 "):
        raise ValueError("layout runtime version mismatch")
    with tempfile.TemporaryDirectory(prefix="plm-caddy-layout-cert-") as folder:
        cert, key, config = (Path(folder) / name for name in ("cert.pem", "key.pem", "Caddyfile"))
        synthetic_certificate(cert, key)
        config.write_text(render(template.read_text(encoding="ascii"), cert=cert, key=key,
                                 frontend=output_root / "app/frontend/dist",
                                 api_port=18080, https_port=18443), encoding="ascii")
        result = subprocess.run([str(caddy), "validate", "--config", str(config)],
                                capture_output=True, text=True, errors="replace", env=env, timeout=20)
        if result.returncode:
            raise ValueError("layout rendered Caddyfile validation failed")
    if (verify_source(candidate)["archive_sha256"] != ARCHIVE_SHA256
            or verify_stage(stage, expected_kind=KIND)["payload_file_count"] != len(hashes)):
        raise ValueError("source candidate or stage changed during rehearsal")
    return {"status": "NON_RELEASE_CADDY_ISOLATED_LAYOUT_PASS", "release_eligible": False,
            "candidate_sha256": ARCHIVE_SHA256, "mapping_sha256": mapping_sha256,
            "layout_root": str(output_root), "copied_file_count": len(mapping),
            "python_version": imported, "postgresql_version": pg_version,
            "caddy_version": caddy_version, "synthetic_template_validate": True,
            "install_authorized": False, "formal_install_performed": False,
            "services_changed": False, "database_started": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(rehearse(args.candidate, args.stage, args.output_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
